import os
import chromadb

client = chromadb.PersistentClient(path="./vectordb")
collection = client.get_or_create_collection("docs")

def chunk_text(text, size=200, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+size])
        chunks.append(chunk)
        i += size - overlap
    return chunks

total = 0
for filename in os.listdir("docs"):
    if filename.endswith(".txt"):
        with open(f"docs/{filename}", "r") as f:
            text = f.read()

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk],
                ids=[f"{filename}-chunk-{i}"]
            )
        print(f"Ingested {filename} → {len(chunks)} chunks")
        total += len(chunks)

print(f"\nDone. {total} chunks stored in vectordb/")
