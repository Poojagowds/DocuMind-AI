import requests

url = "http://localhost:11434/api/embeddings"

data = {
    "model": "nomic-embed-text",
    "prompt": "Artificial Intelligence helps computers understand information."
}

response = requests.post(url, json=data)

result = response.json()

print("Embedding generated successfully!")
print("Number of values:", len(result["embedding"]))
print("First five values:", result["embedding"][:5])