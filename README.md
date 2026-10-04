# HackYeah-
A repository made primarily for a Krakow based Hackathon HackYeah!

## Run the live demo (Windows)

Double-click **`start_demo.bat`**: it opens a tunnel to the GPU server's LLM (if reachable),
starts the backend (:8000) and the frontend (:3000) in live mode, resets the demo and opens
Alice's mailbox and the admin console (press **D** there for the demo controls).
**`stop_demo.bat`** stops it all.

Check the whole demo through the real UI before presenting (headless Chromium, ~1 min):

```bash
pip install playwright && python -m playwright install chromium   # once
python scripts/ui_demo_test.py
```

Explanations for new emails come from the GPU server's Qwen 14B (~5 s), else Ollama's
qwen2.5:3b on the laptop (~30-60 s), else templates; demo emails use cached LLM text.
See `docs/PERSON_B.md` for the scoring/ML/LLM details.
