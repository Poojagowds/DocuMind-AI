
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import PDFDocument, ChatMessage
from .rag import store_pdf_chunks, search_pdf, is_pdf_indexed

import fitz
import requests

from reportlab.pdfgen import canvas
from io import BytesIO


# --------------------------------
# 1. AI PDF SUMMARY
# --------------------------------

def generate_summary(text):

    url = "http://localhost:11434/api/generate"

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

    data = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False
    }

    try:
        print("Starting AI summary...", flush=True)

        response = requests.post(
            url,
            json=data,
            timeout=300
        )

        response.raise_for_status()

        result = response.json()

        summary = result.get("response", "").strip()

        if not summary:
            return "AI service returned an empty response."

        print("AI summary completed!", flush=True)

        return summary

    except requests.exceptions.Timeout:
        print("AI summary timed out.", flush=True)
        return "AI summary timed out. Please try again."

    except requests.exceptions.ConnectionError:
        print("Ollama connection failed.", flush=True)
        return "Ollama is not running. Please start Ollama."

    except requests.exceptions.RequestException as error:
        print("AI summary error:", error, flush=True)
        return "Unable to generate summary due to an AI service error."

    except (ValueError, KeyError) as error:
        print("Invalid AI response:", error, flush=True)
        return "AI service returned an invalid response."


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

    url = "http://localhost:11434/api/generate"

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

    Instructions:
    1. Give a clear and simple answer.
    2. Do not invent information.
    3. If the answer is unavailable, clearly say so.
    4. Do not mention page numbers in your answer.
    5. Do not create your own source citations.

    Document Content:
    {document_text}

    Question:
    {question}

    Answer:
    """

    data = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(
            url,
            json=data,
            timeout=300
        )

        response.raise_for_status()

        result = response.json()

        ai_answer = result.get("response", "").strip()

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

    except requests.exceptions.Timeout:
        return "AI response timed out. Please try again."

    except requests.exceptions.ConnectionError:
        return "Ollama is not running. Please start Ollama."

    except requests.exceptions.RequestException as error:
        print("AI answer error:", error, flush=True)
        return "Unable to generate an answer due to an AI service error."

    except (ValueError, KeyError):
        return "AI service returned an invalid response."


# --------------------------------
# 4. DASHBOARD AND PDF UPLOAD
# --------------------------------

def home(request):

    print("HOME VIEW STARTED:", request.method, flush=True)

    extracted_text = ""
    summary = ""
    upload_error = ""

    if request.method == "POST":

        print("UPLOAD REQUEST RECEIVED", flush=True)

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

                # Generate summary first
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

                # Index PDF only ONCE
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

                # Redirect after successful upload processing
                return redirect("home")

            except ValueError as error:

                upload_error = str(error)

                print("PDF upload error:", error, flush=True)

                file_name = document.pdf_file.name
                file_storage = document.pdf_file.storage

                document.delete()

                try:
                    file_storage.delete(file_name)

                except PermissionError:
                    print(
                        "File is locked. Delete it manually later.",
                        flush=True
                    )

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

    # --------------------------------
    # 5. DASHBOARD DOCUMENTS AND FILTERS
    # --------------------------------

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
# 6. VIEW SAVED SUMMARY
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
# 7. CHAT WITH PDF
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

                print("RAG error:", repr(error), flush=True)

                answer = (
                    "Unable to process your question. "
                    "Please check that Ollama and ChromaDB are working."
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
# 8. DOWNLOAD SUMMARY AS PDF
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
# 9. DELETE DOCUMENT
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
            where={"document_id": str(document.id)}
        )

    except Exception as error:

        print("ChromaDB deletion error:", error, flush=True)

    document.pdf_file.delete(save=False)

    document.delete()

    return redirect("home")


# --------------------------------
# 10. OPEN SELECTED PDF CHAT
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
# 11. CLEAR CHAT HISTORY
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
