def split_text_into_chunks(text, chunk_size=800, overlap=100):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        chunks.append(chunk)

        start = end - overlap

    return chunks


sample_text = """
Artificial Intelligence is a technology that helps computers
perform tasks that normally require human intelligence.
It is used in healthcare, education, banking and transportation.
Machine learning is one important part of Artificial Intelligence.
"""

chunks = split_text_into_chunks(sample_text)

print("Total chunks:", len(chunks))

for number, chunk in enumerate(chunks, start=1):
    print("\nChunk", number)
    print(chunk)