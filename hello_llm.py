from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

import os

docs = ""
for filename in os.listdir("docs"):
    if filename.endswith(".txt"):
        with open(f"docs/{filename}", "r") as f:
            docs += f"\n\n--- {filename} ---\n{f.read()}"

history = [
    {"role": "system", "content": f"You are a DevOps expert. Use these documents to answer questions:\n\n{docs}\n\nIMPORTANT: If the answer is not in the documents, say 'I don't have that in my docs. Please add it.' Do not make anything up."}
]

print("DevOps Assistant (type 'quit' to exit)\n")

while True:
    question = input("You: ")

    if question.lower() == "quit":
        break

    history.append({"role": "user", "content": question})

    if len(history) > 11:
        history = [history[0]] + history[-10:]

    response = client.chat.completions.create(
        model="llama3.2",
        messages=history
    )

    answer = response.choices[0].message.content
    history.append({"role": "assistant", "content": answer})

    print(f"\nAssistant: {answer}\n")
