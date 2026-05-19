import os
import subprocess
import json
import time
import logging
from openai import OpenAI
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(
    filename="requests.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)

ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
client = OpenAI(
    base_url=f"{ollama_host}/v1",
    api_key="ollama"
)

docs = ""
for filename in os.listdir("docs"):
    if filename.endswith(".txt"):
        with open(f"docs/{filename}", "r") as f:
            docs += f"\n\n--- {filename} ---\n{f.read()}"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Question(BaseModel):
    question: str

def run_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
    return result.stdout or result.stderr

def run_agent(question):
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
    start = raw.find("{")
    end = raw.rfind("}") + 1
    try:
        parsed = json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError):
        return raw, None

    if not parsed.get("command"):
        return parsed.get("answer", raw), None

    output = run_command(parsed["command"])

    final = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "user", "content": question},
            {"role": "assistant", "content": f"I ran `{parsed['command']}` and got:\n{output}"},
            {"role": "user", "content": "Now answer my original question based on that output."}
        ]
    )

    return final.choices[0].message.content, parsed["command"]

@app.post("/ask")
def ask(body: Question):
    start = time.time()
    response = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": f"You are a DevOps expert. Use these documents to answer questions:\n\n{docs}\n\nIMPORTANT: If the answer is not in the documents, say 'I don't have that in my docs. Please add it.' Do not make anything up."},
            {"role": "user", "content": body.question}
        ]
    )
    duration = round((time.time() - start) * 1000)
    answer = response.choices[0].message.content
    logging.info(f"endpoint=/ask duration={duration}ms question={body.question!r}")
    return {"answer": answer}

@app.post("/ask/stream")
def ask_stream(body: Question):
    start = time.time()

    def generate():
        stream = client.chat.completions.create(
            model="llama3.2",
            messages=[
                {"role": "system", "content": f"You are a DevOps expert. Use these documents to answer questions:\n\n{docs}\n\nIMPORTANT: If the answer is not in the documents, say 'I don't have that in my docs. Please add it.' Do not make anything up."},
                {"role": "user", "content": body.question}
            ],
            stream=True
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token
        duration = round((time.time() - start) * 1000)
        logging.info(f"endpoint=/ask/stream duration={duration}ms question={body.question!r}")

    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/agent")
def agent(body: Question):
    start = time.time()
    answer, command_run = run_agent(body.question)
    duration = round((time.time() - start) * 1000)
    logging.info(f"endpoint=/agent duration={duration}ms command={command_run!r} question={body.question!r}")
    return {"answer": answer, "command_run": command_run}
