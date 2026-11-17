
import chromadb
import requests
from django.conf import settings
from pathlib import Path


# --------------------------------
# 1. Generate Embeddings using Ollama
# --------------------------------

def get_embedding(text):

    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={
                "model": "nomic-embed-text",
                "prompt": text
            },
            timeout=120
        )

        response.raise_for_status()

        embedding = response.json().get("embedding")

        if not embedding:
            raise ValueError("Ollama returned an empty embedding.")

        print(
            "Ollama embedding generated successfully!",
            flush=True
        )

        return embedding

    except Exception as error:

        print(
            "OLLAMA EMBEDDING ERROR:",
            repr(error),
            flush=True
        )

        return None


# --------------------------------
# 2. Create Persistent ChromaDB
# --------------------------------

CHROMA_PATH = Path(settings.BASE_DIR) / "chroma_db"

client = chromadb.PersistentClient(
    path=str(CHROMA_PATH)
)

collection = client.get_or_create_collection(
    name="pdf_documents_ollama"
)


# --------------------------------
# 3. Split Text into Chunks
# --------------------------------

def split_text_into_chunks(
    text,
    chunk_size=800,
    overlap=100
):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk)

        start = end - overlap

    return chunks


# --------------------------------
# 4. Store PDF Chunks in ChromaDB
# --------------------------------

def store_pdf_chunks(document_id, pages):

    print("Starting PDF indexing...", flush=True)

    # Remove old chunks for this document
    collection.delete(
        where={
            "document_id": str(document_id)
        }
    )

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for page in pages:

        page_number = page["page_number"]

        text = page["text"]

        chunks = split_text_into_chunks(text)

        for chunk_index, chunk in enumerate(chunks):

            print(
                f"Generating embedding: Page {page_number}, "
                f"Chunk {chunk_index + 1}/{len(chunks)}",
                flush=True
            )

            embedding = get_embedding(chunk)

            if embedding is None:

                raise ValueError(
                    "Could not generate PDF embedding using Ollama."
                )

            ids.append(
                f"doc_{document_id}_page_{page_number}_chunk_{chunk_index}"
            )

            documents.append(chunk)

            embeddings.append(embedding)

            metadatas.append({
                "document_id": str(document_id),
                "page_number": page_number,
                "chunk_index": chunk_index
            })

    if ids:

        print("Saving embeddings to ChromaDB...", flush=True)

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    print(
        "PDF indexing completed. Total chunks:",
        len(ids),
        flush=True
    )

    return len(ids)


# --------------------------------
# 5. Search Relevant PDF Chunks
# --------------------------------

def search_pdf(document_id, question):

    print("Generating question embedding...", flush=True)

    question_embedding = get_embedding(question)

    if question_embedding is None:

        raise ValueError(
            "Could not generate question embedding using Ollama."
        )

    print("Searching ChromaDB...", flush=True)

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=5,
        where={
            "document_id": str(document_id)
        }
    )

    relevant_chunks = []

    if results["documents"] and results["documents"][0]:

        for text, metadata in zip(
            results["documents"][0],
            results["metadatas"][0]
        ):

            relevant_chunks.append({
                "text": text,
                "page_number": metadata["page_number"]
            })

    print(
        "Relevant chunks found:",
        len(relevant_chunks),
        flush=True
    )

    return relevant_chunks


# --------------------------------
# 6. Check Whether PDF Is Indexed
# --------------------------------

def is_pdf_indexed(document_id):

    results = collection.get(
        where={
            "document_id": str(document_id)
        },
        limit=1
    )

    return len(results["ids"]) > 0
