# DocuMind AI – AI-Powered PDF Assistant

An intelligent PDF assistant that allows users to upload PDF documents, generate AI-powered summaries, and ask questions about document content using Retrieval-Augmented Generation (RAG).

## 🚀 Live Demo

**Live Application:** https://documind-ai-0z5t.onrender.com

**GitHub Repository:** https://github.com/Poojagowds/DocuMind-AI

## 📌 Project Overview

DocuMind AI simplifies document understanding by combining PDF text extraction, AI summarization, and intelligent question answering.

Users can upload PDF documents and receive meaningful summaries. They can also interact with their documents through a chat interface and receive answers based on the actual PDF content, along with relevant page references.

## ✨ Key Features

- **PDF Upload:** Upload and manage PDF documents.
- **Text Extraction:** Extract text from PDF files using PyMuPDF.
- **AI Summarization:** Generate clear and structured summaries using Gemini.
- **Chat with PDF:** Ask questions about uploaded documents.
- **RAG Implementation:** Retrieve relevant document chunks before generating answers.
- **Semantic Search:** Use embeddings and similarity search to find relevant content.
- **Page References:** Display source page numbers with generated answers.
- **Download Summary:** Download generated summaries as PDF files.
- **Document Management:** View and delete uploaded documents.
- **AI Model Fallback:** Switch to a fallback Gemini model when the primary model is unavailable.

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Django | Web application framework |
| HTML, CSS, JavaScript | Frontend development |
| PyMuPDF | PDF text extraction |
| Gemini API | AI summarization and answers |
| Ollama | Local AI model execution |
| Embeddings | Document representation |
| SQLite | Lightweight vector storage |
| Cloudinary | PDF file storage |
| Render | Cloud deployment |

## ⚙️ How It Works

1. **Upload:** The user uploads a PDF document.
2. **Extraction:** PyMuPDF extracts text from the document page by page.
3. **Chunking:** Extracted text is divided into smaller chunks.
4. **Embedding:** Embeddings are generated for document chunks.
5. **Storage:** Document chunks and their embeddings are stored for retrieval.
6. **Retrieval:** When a user asks a question, relevant chunks are retrieved using similarity search.
7. **AI Generation:** Gemini uses the retrieved content to generate a relevant answer.
8. **Response:** The answer is displayed with PDF page references.

## 🧠 Understanding RAG

Retrieval-Augmented Generation (RAG) combines information retrieval with AI-generated responses.

Instead of asking an AI model to answer from general knowledge alone, DocuMind AI first searches the uploaded document for relevant information and then provides that information to the AI model.

This helps generate answers grounded in the uploaded PDF.

## 💻 Local Installation

**1. Clone the repository**

```bash
git clone https://github.com/Poojagowds/DocuMind-AI.git
cd DocuMind-AI
```

**2. Create a virtual environment**

```bash
python -m venv venv
```

**3. Activate the environment**

Windows:

```bash
venv\Scripts\activate
```

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

**5. Configure environment variables**

Add the required API keys and storage credentials to your environment configuration.

At minimum:

```env
GEMINI_API_KEY=your_gemini_api_key
```

Configure the remaining settings required by your project.

**6. Run database migrations**

```bash
python manage.py migrate
```

**7. Start the development server**

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## 🎯 Project Objective

The objective of DocuMind AI is to make information extraction and document understanding faster and easier through AI-powered summarization and conversational document interaction.

## 👩‍💻 Developer

Developed as a Python and Django-based AI project to explore document processing, embeddings, Retrieval-Augmented Generation, and Large Language Model integration.
