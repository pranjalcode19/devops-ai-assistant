import subprocess
import json
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

def run_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
    return result.stdout or result.stderr

def run_agent(question):
    # Step 1: Ask model which command to run
    plan = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": """You are a DevOps assistant.
When asked a question that needs live system data, respond with ONLY a JSON object like:
{"command": "df -h"}
If no command is needed, respond with:
{"command": null, "answer": "your answer here"}"""},
            {"role": "user", "content": question}
        ]
    )

    raw = plan.choices[0].message.content.strip()

    # Extract JSON from response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    parsed = json.loads(raw[start:end])

    if not parsed.get("command"):
        return parsed.get("answer", raw)

    # Step 2: Run the command
    print(f"[Agent running: {parsed['command']}]")
    output = run_command(parsed["command"])

    # Step 3: Ask model to interpret the output
    final = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "user", "content": question},
            {"role": "assistant", "content": f"I ran `{parsed['command']}` and got:\n{output}"},
            {"role": "user", "content": "Now answer my original question based on that output."}
        ]
    )

    return final.choices[0].message.content

print(run_agent("How much disk space is available on my machine?"))
