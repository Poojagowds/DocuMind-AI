import requests

url = "http://localhost:11434/api/generate"

data = {
    "model": "llama3.2:3b",
    "prompt": "Explain Artificial Intelligence in two simple sentences.",
    "stream": False
}

response = requests.post(url, json=data)

result = response.json()

print(result["response"])