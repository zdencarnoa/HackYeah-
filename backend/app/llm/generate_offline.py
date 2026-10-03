"""Run an open-source chat model over prompts.jsonl (GPU box; standalone, no app imports).

    python generate_offline.py prompts.jsonl responses.jsonl [--model Qwen/Qwen2.5-14B-Instruct]

Greedy decoding, so the cache is reproducible for a given model.
"""
import argparse
import json
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompts")
    ap.add_argument("out")
    ap.add_argument("--model", default="Qwen/Qwen2.5-14B-Instruct")
    ap.add_argument("--batch-size", type=int, default=16)
    args = ap.parse_args()

    rows = [json.loads(line) for line in open(args.prompts, encoding="utf-8")]
    tok = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    print(f"{len(rows)} prompts, model {args.model}", flush=True)

    t0 = time.time()
    with open(args.out, "w", encoding="utf-8") as out:
        for i in range(0, len(rows), args.batch_size):
            chunk = rows[i:i + args.batch_size]
            texts = [tok.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=True) for r in chunk]
            enc = tok(texts, return_tensors="pt", padding=True).to("cuda")
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=400, do_sample=False, pad_token_id=tok.eos_token_id)
            for r, seq in zip(chunk, gen[:, enc["input_ids"].shape[1]:]):
                out.write(json.dumps({"fingerprint": r["fingerprint"], "kind": r["kind"],
                                      "text": tok.decode(seq, skip_special_tokens=True)}) + "\n")
            print(f"{min(i + args.batch_size, len(rows))}/{len(rows)} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
