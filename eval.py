import os
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

# Load documents
docs = ""
for filename in os.listdir("docs"):
    if filename.endswith(".txt"):
        with open(f"docs/{filename}", "r") as f:
            docs += f"\n\n--- {filename} ---\n{f.read()}"

def ask(question):
    response = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": f"You are a DevOps expert. Use these documents to answer questions:\n\n{docs}\n\nIMPORTANT: If the answer is not in the documents, say 'I don't have that in my docs. Please add it.' Do not make anything up."},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content

# Test cases: question + what the correct answer must contain
TEST_CASES = [
    {"question": "How do I roll back a deployment?",         "must_contain": "kubectl rollout undo"},
    {"question": "What monitoring tool do we use?",          "must_contain": "datadog"},
    {"question": "How long do I have to acknowledge a P1?",  "must_contain": "5 minutes"},
    {"question": "What tool do we use for source control?",  "must_contain": "github"},
    {"question": "What do I do when Kubernetes pods crash?", "must_contain": "kubernetes"},
]

print("Running evals...\n")

passed = 0
for test in TEST_CASES:
    answer = ask(test["question"])
    correct = test["must_contain"].lower() in answer.lower()
    status = "PASS" if correct else "FAIL"
    if correct:
        passed += 1
    print(f"[{status}] {test['question']}")
    if not correct:
        print(f"       Expected to contain: '{test['must_contain']}'")
        print(f"       Got: {answer[:100]}...")
    print()

print(f"Score: {passed}/{len(TEST_CASES)} ({passed/len(TEST_CASES):.0%})")
