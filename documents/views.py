
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import PDFDocument, ChatMessage
from .rag import store_pdf_chunks, search_pdf, is_pdf_indexed

import fitz
import requests
import os

from google import genai
from reportlab.pdfgen import canvas
from io import BytesIO


# --------------------------------
# GEMINI CLIENT
# --------------------------------

def get_gemini_client():

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing.")

    return genai.Client(api_key=api_key)


# --------------------------------
# 1. AI PDF SUMMARY
# --------------------------------

def generate_summary(text):

    prompt = f"""
You are a professional document summarisation assistant.

Analyse the following document and provide:

1. Main Topic
2. Short Overview
3. Important Points
4. Key Information
5. Conclusion

Use simple English and clear bullet points.

Document:
{text}
"""

    if os.getenv("RENDER", "False").lower() == "true":

        try:
            client = get_gemini_client()

            print("Starting Gemini summary...", flush=True)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            summary = (response.text or "").strip()

            if not summary:
                return "AI service returned an empty response."

            print("Gemini summary completed!", flush=True)

            return summary

        except Exception as error:
            print("Gemini summary error:", repr(error), flush=True)

            return "Gemini is temporarily unavailable. Please try again later."

    # Local Ollama

    try:

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False
            },
            timeout=300
        )

        response.raise_for_status()

        summary = response.json().get("response", "").strip()

        if not summary:
            return "AI service returned an empty response."

        return summary

    except requests.exceptions.RequestException as error:

        print("Ollama summary error:", repr(error), flush=True)

        return "Unable to generate summary. Please check Ollama."


# --------------------------------
# 2. EXTRACT PDF PAGES
# --------------------------------

def extract_pdf_pages(pdf_path):

    pages = []
    pdf = None

    try:

        print("Opening PDF...", flush=True)

        pdf = fitz.open(pdf_path)

        print("PDF opened successfully!", flush=True)
        print("Number of pages:", pdf.page_count, flush=True)

        if pdf.is_encrypted:
            raise ValueError(
                "Password-protected PDFs are not supported."
            )

        if pdf.page_count == 0:
            raise ValueError("This PDF has no pages.")

        for page_number, page in enumerate(pdf, start=1):

            page_text = page.get_text().strip()

            if page_text:

                pages.append({
                    "page_number": page_number,
                    "text": page_text
                })

    except ValueError:
        raise

    except Exception as error:

        print("PDF extraction error:", repr(error), flush=True)

        raise ValueError(
            "Invalid or corrupted PDF. Please upload a valid PDF."
        )

    finally:

        if pdf is not None:
            pdf.close()

    if not pages:

        raise ValueError(
            "No readable text found. This PDF may contain scanned images."
        )

    return pages


# --------------------------------
# 3. AI ANSWER USING RAG
# --------------------------------

def generate_answer(relevant_chunks, question):

    if not relevant_chunks:

        return "I could not find relevant information in this document."

    document_text = ""

    for chunk in relevant_chunks:

        document_text += (
            f"\n--- PDF Page {chunk['page_number']} ---\n"
        )

        document_text += chunk["text"]

    prompt = f"""
You are a helpful PDF assistant.

Answer using only the provided PDF content.
Do not invent information.
If the answer is unavailable, clearly say so.
Give a clear and simple answer.

Document Content:
{document_text}

Question:
{question}

Answer:
"""

    try:

        if os.getenv("RENDER", "False").lower() == "true":

            client = get_gemini_client()

            print("Generating Gemini answer...", flush=True)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            ai_answer = (response.text or "").strip()

        else:

            print("Generating local Ollama answer...", flush=True)

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=300
            )

            response.raise_for_status()

            ai_answer = response.json().get(
                "response", ""
            ).strip()

        if not ai_answer:

            return "AI service returned an empty response."

        source_pages = sorted(set(
            chunk["page_number"]
            for chunk in relevant_chunks
        ))

        page_references = ", ".join(
            str(page) for page in source_pages
        )

        return (
            f"{ai_answer}\n\n"
            f"Source: PDF page(s) {page_references}"
        )

    except Exception as error:

        print("AI answer error:", repr(error), flush=True)

        return (
            "Unable to generate an answer right now. "
            "Please try again later."
        )


# --------------------------------
# 4. DASHBOARD AND PDF UPLOAD
# --------------------------------

def home(request):

    print("HOME FUNCTION IS RUNNING", flush=True)

    extracted_text = ""
    summary = ""
    upload_error = ""

    if request.method == "POST":

        uploaded_file = request.FILES.get("pdf_file")

        if not uploaded_file:

            upload_error = "Please select a PDF file."

        elif not uploaded_file.name.lower().endswith(".pdf"):

            upload_error = "Only PDF files are allowed."

        else:

            document = PDFDocument(
                title=uploaded_file.name,
                pdf_file=uploaded_file
            )

            try:

                document.save()

                print("PDF saved. Extracting text...", flush=True)

                pages = extract_pdf_pages(
                    document.pdf_file.path
                )

                for page in pages:

                    extracted_text += (
                        f"\n--- Page {page['page_number']} ---\n"
                    )

                    extracted_text += page["text"]

                # Generate summary

                summary = generate_summary(extracted_text)

                print(
                    "AI SUMMARY RESULT:",
                    repr(summary[:300]),
                    flush=True
                )

                summary_errors = (
                    "AI summary timed out",
                    "Ollama is not running",
                    "Unable to generate summary",
                    "AI service returned",
                    "Gemini is temporarily unavailable",
                )

                if summary and not summary.startswith(summary_errors):

                    document.is_summarized = True
                    document.summary_text = summary

                    document.save(
                        update_fields=[
                            "is_summarized",
                            "summary_text"
                        ]
                    )

                else:

                    upload_error = summary

                # Index PDF in ChromaDB

                print("Starting PDF indexing...", flush=True)

                count = store_pdf_chunks(
                    document.id,
                    pages
                )

                print(
                    "PDF indexing completed. Chunks:",
                    count,
                    flush=True
                )

                return redirect("home")

            except ValueError as error:

                upload_error = str(error)

                print("PDF upload error:", repr(error), flush=True)

                document.delete()

            except Exception as error:

                print(
                    "Upload processing error:",
                    repr(error),
                    flush=True
                )

                upload_error = (
                    "PDF was uploaded, but processing failed. "
                    "Please check the terminal for details."
                )

    # Dashboard documents

    all_documents = PDFDocument.objects.all().order_by(
        "-uploaded_at"
    )

    total_documents = all_documents.count()

    summarized_documents = PDFDocument.objects.filter(
        is_summarized=True
    ).count()

    search_query = request.GET.get(
        "search", ""
    ).strip()

    documents = all_documents

    if search_query:

        documents = documents.filter(
            title__icontains=search_query
        )

    status_filter = request.GET.get("status", "")

    if status_filter == "summarized":

        documents = documents.filter(
            is_summarized=True
        )

    elif status_filter == "not_summarized":

        documents = documents.filter(
            is_summarized=False
        )

    return render(
        request,
        "documents/home.html",
        {
            "extracted_text": extracted_text,
            "documents": documents,
            "summary": summary,
            "total_documents": total_documents,
            "summarized_documents": summarized_documents,
            "search_query": search_query,
            "status_filter": status_filter,
            "upload_error": upload_error,
        }
    )


# --------------------------------
# 5. VIEW SAVED SUMMARY
# --------------------------------

def view_summary(request, document_id):

    document = get_object_or_404(
        PDFDocument,
        id=document_id
    )

    return render(
        request,
        "documents/summary.html",
        {
            "document": document
        }
    )


# --------------------------------
# 6. CHAT WITH PDF
# --------------------------------

def chat_with_pdf(request, document_id):

    document = get_object_or_404(
        PDFDocument,
        id=document_id
    )

    if request.method == "POST":

        question = request.POST.get(
            "question", ""
        ).strip()

        if question:

            try:

                if not is_pdf_indexed(document.id):

                    print(
                        "PDF is not indexed. Starting indexing...",
                        flush=True
                    )

                    pages = extract_pdf_pages(
                        document.pdf_file.path
                    )

                    count = store_pdf_chunks(
                        document.id,
                        pages
                    )

                    if count == 0:

                        raise ValueError(
                            "No PDF chunks were created."
                        )

                relevant_chunks = search_pdf(
                    document.id,
                    question
                )

                answer = generate_answer(
                    relevant_chunks,
                    question
                )

            except Exception as error:

                print(
                    "RAG error:",
                    repr(error),
                    flush=True
                )

                answer = (
                    "Unable to process your question. "
                    "Please check the server logs."
                )

            ChatMessage.objects.create(
                document=document,
                question=question,
                answer=answer
            )

    messages = ChatMessage.objects.filter(
        document=document
    ).order_by("created_at")

    return render(
        request,
        "documents/chat.html",
        {
            "document": document,
            "messages": messages
        }
    )


# --------------------------------
# 7. DOWNLOAD SUMMARY AS PDF
# --------------------------------

def download_summary(request, document_id):

    document = get_object_or_404(
        PDFDocument,
        id=document_id
    )

    buffer = BytesIO()

    pdf = canvas.Canvas(buffer)

    pdf.setTitle("AI Generated Summary")

    pdf.setFont("Helvetica-Bold", 16)

    pdf.drawString(
        50, 800,
        "DocuMind AI - Summary"
    )

    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawString(
        50, 770,
        document.title[:80]
    )

    pdf.setFont("Helvetica", 10)

    text_object = pdf.beginText(50, 740)

    text_object.setLeading(15)

    for line in document.summary_text.splitlines():

        text_object.textLine(line[:100])

    pdf.drawText(text_object)

    pdf.save()

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="summary_{document.id}.pdf"'
    )

    return response


# --------------------------------
# 8. DELETE DOCUMENT
# --------------------------------

@require_POST
def delete_document(request, document_id):

    document = get_object_or_404(
        PDFDocument,
        id=document_id
    )

    try:

        from .rag import collection

        collection.delete(
            where={
                "document_id": str(document.id)
            }
        )

    except Exception as error:

        print(
            "ChromaDB deletion error:",
            repr(error),
            flush=True
        )

    document.pdf_file.delete(save=False)

    document.delete()

    return redirect("home")


# --------------------------------
# 9. OPEN SELECTED PDF CHAT
# --------------------------------

def open_selected_chat(request):

    if request.method == "POST":

        document_id = request.POST.get("document_id")

        if document_id:

            return redirect(
                "chat_with_pdf",
                document_id=document_id
            )

    return redirect("home")


# --------------------------------
# 10. CLEAR CHAT HISTORY
# --------------------------------

@require_POST
def clear_chat(request, document_id):

    document = get_object_or_404(
        PDFDocument,
        id=document_id
    )

    ChatMessage.objects.filter(
        document=document
    ).delete()

    return redirect(
        "chat_with_pdf",
        document_id=document.id
    )
