"""Minimal OpenAI-compatible chat server for an open-source model (GPU box; standalone).

    python serve_openai.py --model Qwen/Qwen2.5-14B-Instruct --port 8001

Listens on 127.0.0.1 only; reach it from the laptop through an SSH tunnel:
    ssh -N -L 8001:localhost:8001 lambda-gpu
then set LLM_SERVER_URL=http://localhost:8001/v1 for the backend.
Implements just POST /v1/chat/completions (non-streaming) and GET /health.
"""
import argparse
import threading
import time

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict]
    temperature: float = 0.0
    max_tokens: int = 400


def build_app(model_name: str) -> FastAPI:
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16, device_map="cuda").eval()
    lock = threading.Lock()  # one generation at a time is plenty for a demo
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True, "model": model_name}

    @app.post("/v1/chat/completions")
    def chat(req: ChatRequest):
        text = tok.apply_chat_template(req.messages, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to("cuda")
        t0 = time.time()
        with lock, torch.no_grad():
            out = model.generate(**enc, max_new_tokens=min(req.max_tokens, 800), do_sample=req.temperature > 0,
                                 temperature=req.temperature or None, pad_token_id=tok.eos_token_id)
        answer = tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        return {"object": "chat.completion", "model": model_name, "created": int(t0),
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": answer}}],
                "usage": {"latency_s": round(time.time() - t0, 2)}}

    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-14B-Instruct")
    ap.add_argument("--port", type=int, default=8001)
    args = ap.parse_args()
    uvicorn.run(build_app(args.model), host="127.0.0.1", port=args.port)
