import json
import math
import os
import sqlite3
from pathlib import Path

import requests
from django.conf import settings
from google import genai


# --------------------------------
# 1. LIGHTWEIGHT SQLITE VECTOR STORE
# --------------------------------

DB_PATH = Path(settings.BASE_DIR) / "documind_vectors.sqlite3"


def get_connection():
    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=30
    )

    connection.execute("""
        CREATE TABLE IF NOT EXISTS pdf_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_pdf_document
        ON pdf_chunks(document_id)
    """)

    return connection


# --------------------------------
# 2. GENERATE EMBEDDINGS
# --------------------------------

def get_embedding(text):

    if os.getenv("RENDER", "False").lower() == "true":

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing.")

        client = genai.Client(api_key=api_key)

        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text
        )

        if not response.embeddings:
            raise ValueError("Gemini returned no embedding.")

        return list(response.embeddings[0].values)

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
        raise ValueError("Ollama returned no embedding.")

    return embedding


# --------------------------------
# 3. SPLIT TEXT INTO SMALL CHUNKS
# --------------------------------

def split_text_into_chunks(
    text,
    chunk_size=800,
    overlap=100
):

    chunks = []

    step = max(1, chunk_size - overlap)

    for start in range(0, len(text), step):

        chunk = text[start:start + chunk_size]

        if chunk.strip():
            chunks.append(chunk)

    return chunks


# --------------------------------
# 4. DELETE OLD PDF INDEX
# --------------------------------

def delete_pdf_chunks(document_id):

    connection = get_connection()

    try:
        connection.execute(
            "DELETE FROM pdf_chunks WHERE document_id = ?",
            (str(document_id),)
        )

        connection.commit()

    finally:
        connection.close()


# --------------------------------
# 5. STORE PDF CHUNKS
# --------------------------------

def store_pdf_chunks(document_id, pages):

    print("Starting lightweight PDF indexing...", flush=True)

    connection = get_connection()

    try:

        connection.execute(
            "DELETE FROM pdf_chunks WHERE document_id = ?",
            (str(document_id),)
        )

        connection.commit()

        total_chunks = 0

        for page in pages:

            page_number = page["page_number"]
            text = page["text"]

            chunks = split_text_into_chunks(text)

            for chunk_index, chunk in enumerate(chunks):

                print(
                    f"Embedding page {page_number}, "
                    f"chunk {chunk_index + 1}/{len(chunks)}",
                    flush=True
                )

                embedding = get_embedding(chunk)

                row_id = (
                    f"doc_{document_id}_"
                    f"page_{page_number}_"
                    f"chunk_{chunk_index}"
                )

                connection.execute(
                    """
                    INSERT INTO pdf_chunks
                    (id, document_id, page_number,
                     chunk_index, text, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_id,
                        str(document_id),
                        page_number,
                        chunk_index,
                        chunk,
                        json.dumps(embedding)
                    )
                )

                # Save each embedding immediately.
                connection.commit()

                total_chunks += 1

        print(
            "PDF indexing completed. Total chunks:",
            total_chunks,
            flush=True
        )

        return total_chunks

    except Exception:

        connection.execute(
            "DELETE FROM pdf_chunks WHERE document_id = ?",
            (str(document_id),)
        )

        connection.commit()

        raise

    finally:
        connection.close()


# --------------------------------
# 6. COSINE SIMILARITY
# --------------------------------

def cosine_similarity(vector_a, vector_b):

    if len(vector_a) != len(vector_b):
        return 0

    dot_product = sum(
        a * b for a, b in zip(vector_a, vector_b)
    )

    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        return 0

    return dot_product / (norm_a * norm_b)


# --------------------------------
# 7. SEARCH RELEVANT PDF CHUNKS
# --------------------------------

def search_pdf(document_id, question):

    print("Generating question embedding...", flush=True)

    question_embedding = get_embedding(question)

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT text, page_number, embedding
            FROM pdf_chunks
            WHERE document_id = ?
            """,
            (str(document_id),)
        ).fetchall()

    finally:
        connection.close()

    scored_chunks = []

    for text, page_number, stored_embedding in rows:

        embedding = json.loads(stored_embedding)

        score = cosine_similarity(
            question_embedding,
            embedding
        )

        scored_chunks.append({
            "text": text,
            "page_number": page_number,
            "score": score
        })

    scored_chunks.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    relevant_chunks = []

    for chunk in scored_chunks[:5]:

        relevant_chunks.append({
            "text": chunk["text"],
            "page_number": chunk["page_number"]
        })

    print(
        "Relevant chunks found:",
        len(relevant_chunks),
        flush=True
    )

    return relevant_chunks


# --------------------------------
# 8. CHECK PDF INDEX STATUS
# --------------------------------

def is_pdf_indexed(document_id):

    connection = get_connection()

    try:

        result = connection.execute(
            """
            SELECT 1
            FROM pdf_chunks
            WHERE document_id = ?
            LIMIT 1
            """,
            (str(document_id),)
        ).fetchone()

        return result is not None

    finally:
        connection.close()