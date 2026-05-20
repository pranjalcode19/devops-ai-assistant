import os
import sys
from openai import OpenAI

client = OpenAI(
    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
    api_key="ollama"
)

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

TEST_CASES = [
    {"question": "How do I roll back a deployment?",         "must_contain": "kubectl rollout undo"},
    {"question": "What monitoring tool do we use?",          "must_contain": "datadog"},
    {"question": "How long do I have to acknowledge a P1?",  "must_contain": "5 minutes"},
    {"question": "What tool do we use for source control?",  "must_contain": "github"},
    {"question": "What do I do when Kubernetes pods crash?", "must_contain": "kubernetes"},
]

PASS_THRESHOLD = 0.8

print("Running CI evals...\n")

passed = 0
for test in TEST_CASES:
    answer = ask(test["question"])
    correct = test["must_contain"].lower() in answer.lower()
    status = "PASS" if correct else "FAIL"
    if correct:
        passed += 1
    print(f"[{status}] {test['question']}")
    if not correct:
        print(f"       Expected: '{test['must_contain']}'")
        print(f"       Got: {answer[:120]}...")
    print()

score = passed / len(TEST_CASES)
print(f"Score: {passed}/{len(TEST_CASES)} ({score:.0%})")

if score < PASS_THRESHOLD:
    print(f"\nFAILED: Score {score:.0%} is below threshold {PASS_THRESHOLD:.0%}")
    print("Merge blocked.")
    sys.exit(1)
else:
    print(f"\nPASSED: Score {score:.0%} meets threshold {PASS_THRESHOLD:.0%}")
    print("Merge allowed.")
    sys.exit(0)
