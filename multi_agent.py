import os
import subprocess
import json
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

# Load docs once
docs = ""
for filename in os.listdir("docs"):
    if filename.endswith(".txt"):
        with open(f"docs/{filename}", "r") as f:
            docs += f"\n\n--- {filename} ---\n{f.read()}"


def docs_agent(question):
    """Searches internal runbooks and returns relevant information."""
    response = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": f"You are a knowledge agent. Search these documents and extract only facts relevant to the question. Be concise.\n\n{docs}"},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content


def system_agent(question):
    """Runs shell commands to get live system data."""
    plan = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": """You are a system agent running on macOS. Decide which shell command answers this question.
Use macOS-compatible commands only: df -h (disk), vm_stat (memory), top -l 1 (CPU), uptime, ps aux, uname -a.
Reply with ONLY JSON: {"command": "the command"}
If no command needed: {"command": null}"""},
            {"role": "user", "content": question}
        ]
    )
    raw = plan.choices[0].message.content.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    try:
        parsed = json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError):
        return "Could not determine a system command."

    if not parsed.get("command"):
        return "No live system data needed."

    print(f"  [system_agent running: {parsed['command']}]")
    result = subprocess.run(parsed["command"], shell=True, capture_output=True, text=True, timeout=10)
    return result.stdout or result.stderr


def coordinator(question):
    """Routes question to relevant agents and combines their answers."""
    print(f"\nQuestion: {question}")
    print("-" * 50)

    # Decide which agents to use
    routing = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": """You are a coordinator. Decide which agents to use for this question.
Reply with ONLY JSON: {"use_docs": true/false, "use_system": true/false}
use_docs: true if answer might be in internal runbooks/docs
use_system: true if answer requires live system data (disk, memory, processes, etc.)
When a question asks to compare system state against guidelines (e.g. "is disk healthy"), set BOTH to true."""},
            {"role": "user", "content": question}
        ]
    )
    raw = routing.choices[0].message.content.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    try:
        route = json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError):
        route = {"use_docs": True, "use_system": False}

    print(f"  [coordinator routing: docs={route.get('use_docs')} system={route.get('use_system')}]")

    # Collect results from relevant agents
    agent_results = []

    if route.get("use_docs"):
        print("  [docs_agent searching runbooks...]")
        docs_result = docs_agent(question)
        agent_results.append(f"From internal docs:\n{docs_result}")

    if route.get("use_system"):
        print("  [system_agent fetching live data...]")
        system_result = system_agent(question)
        agent_results.append(f"From live system:\n{system_result}")

    if not agent_results:
        agent_results.append("No agent data available.")

    # Combine and synthesize final answer
    combined = "\n\n".join(agent_results)
    final = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": "You are a senior DevOps engineer. Synthesize the agent findings into a clear, actionable answer."},
            {"role": "user", "content": f"Question: {question}\n\nAgent findings:\n{combined}"}
        ]
    )

    answer = final.choices[0].message.content
    print(f"\nAnswer:\n{answer}\n")
    return answer


if __name__ == "__main__":
    # Test 1: docs only
    coordinator("What is the process to get access to Jenkins?")

    # Test 2: system only
    coordinator("How much memory is my machine using?")

    # Test 3: both agents needed
    coordinator("Is my disk space healthy based on our runbook guidelines?")
