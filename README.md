# secure-ai-deployment

Lab for the Pharos-CY training *Secure AI Deployment & Responsible AI Systems*.
One small agent, two profiles (`unsafe` / `hardened`). Everything runs locally.

```
pip install -r requirements.txt           # openai, pyyaml, matplotlib, jupyter
cp config.example.yaml config.yaml         # then put your key in model.api_key, or set OPENROUTER_API_KEY
python mock/seed.py                        # build the mock company (SQLite DB + file share)
python test_lab.py                         # policy layer checks, no model needed
python notebooks/koda_lab.py               # the browser course's lab (shared by module 02 and the model benchmark), same idea
python notebooks/koda_toolbox.py           # module 03's lab: the ten-tool toolbox, its exercises, model answers and wrong answers
python -m lab.agent --profile unsafe   "Look up customer 42 for me"
python -m lab.agent --profile hardened "Look up customer 42 for me"
python -m lab.agent --replay traces/<file>.jsonl   # stage fallback to a video demo
jupyter lab notebooks/02_prompt_injection.ipynb    # the first teaching notebook
```

Point `config.yaml` at any OpenAI-compatible endpoint (LM Studio, Ollama, a cloud key). If `config.yaml` is absent the lab falls back to `config.example.yaml`, which reads the key from the `OPENROUTER_API_KEY` environment variable.

`mock/` is fake: a poisoned CRM record (id 42), a "secrets" folder, a "production" DB. Delete and re-seed freely.
