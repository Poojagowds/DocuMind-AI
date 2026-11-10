import chromadb
import requests

# Connect to Ollama
def get_embedding(text):
    url = "http://localhost:11434/api/embeddings"

    data = {
        "model": "nomic-embed-text",
        "prompt": text
    }

    response = requests.post(url, json=data)
    response.raise_for_status()

    return response.json()["embedding"]


# Create ChromaDB database
client = chromadb.PersistentClient(path="chroma_test_db")

collection = client.get_or_create_collection(
    name="pdf_test"
)


# Sample PDF text chunks
chunks = [
    "Artificial Intelligence helps computers perform intelligent tasks.",
    "Machine learning is a branch of Artificial Intelligence.",
    "Python is a popular programming language used in AI."
]


# Generate embeddings and store chunks
for index, chunk in enumerate(chunks):

    embedding = get_embedding(chunk)

    collection.add(
        ids=[f"chunk_{index}"],
        embeddings=[embedding],
        documents=[chunk]
    )

print("Chunks stored successfully!")


# Search for relevant information
question = "What is machine learning?"

question_embedding = get_embedding(question)

results = collection.query(
    query_embeddings=[question_embedding],
    n_results=2
)

print("\nRelevant information:")

for result in results["documents"][0]:
    print(result)