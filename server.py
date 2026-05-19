import os
import subprocess
import json
import time
import logging
import uuid
import chromadb
from openai import OpenAI
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

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

chroma = chromadb.PersistentClient(path="./vectordb")
collection = chroma.get_or_create_collection("docs")

def retrieve(question, n=3):
    results = collection.query(query_texts=[question], n_results=n)
    return "\n\n".join(results["documents"][0])

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

sessions = {}  # session_id -> list of messages
metrics = {"total_requests": 0, "total_latency_ms": 0, "questions": []}

class Question(BaseModel):
    question: str
    session_id: Optional[str] = None

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
    context = retrieve(body.question)

    session_id = body.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = [
            {"role": "system", "content": f"You are a DevOps expert. Use these documents to answer questions:\n\n{context}\n\nIMPORTANT: If the answer is not in the documents, say 'I don't have that in my docs. Please add it.' Do not make anything up."}
        ]

    sessions[session_id].append({"role": "user", "content": body.question})

    if len(sessions[session_id]) > 12:
        sessions[session_id] = [sessions[session_id][0]] + sessions[session_id][-10:]

    response = client.chat.completions.create(
        model="llama3.2",
        messages=sessions[session_id]
    )
    answer = response.choices[0].message.content
    sessions[session_id].append({"role": "assistant", "content": answer})

    score = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": "Rate how confident you are in this answer given the context provided. Reply with only a number from 1-10."},
            {"role": "user", "content": f"Context: {context}\nQuestion: {body.question}\nAnswer: {answer}"}
        ]
    )
    raw_score = score.choices[0].message.content.strip()
    confidence = int("".join(filter(str.isdigit, raw_score))[:2] or 0)

    duration = round((time.time() - start) * 1000)
    metrics["total_requests"] += 1
    metrics["total_latency_ms"] += duration
    metrics["questions"].append(body.question)
    logging.info(f"endpoint=/ask duration={duration}ms session={session_id} confidence={confidence} question={body.question!r}")
    return {"answer": answer, "session_id": session_id, "confidence": confidence}

@app.get("/metrics")
def get_metrics():
    total = metrics["total_requests"]
    avg_latency = round(metrics["total_latency_ms"] / total) if total else 0
    return {
        "total_requests": total,
        "avg_latency_ms": avg_latency,
        "recent_questions": metrics["questions"][-5:]
    }

@app.post("/ask/stream")
def ask_stream(body: Question):
    start = time.time()

    def generate():
        context = retrieve(body.question)
        stream = client.chat.completions.create(
            model="llama3.2",
            messages=[
                {"role": "system", "content": f"You are a DevOps expert. Use these documents to answer questions:\n\n{context}\n\nIMPORTANT: If the answer is not in the documents, say 'I don't have that in my docs. Please add it.' Do not make anything up."},
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
