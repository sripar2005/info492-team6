# Running Demo 3 on a local model (Mac, Apple silicon)

The same prompts and schema run on an open model on your own computer through Ollama, so no project data leaves the machine.

1. Install Ollama from https://ollama.com/download and open it once.
2. In Terminal (or skip this: the `Demo 3 - local models` GitHub workflow runs Llama 3.1 8B and Qwen2.5 7B for free on GitHub's machines):
   ```bash
   ollama pull llama3.1:8b          # about 4.7 GB
   git clone https://github.com/sripar2005/info492-team6.git && cd info492-team6/demo3
   python3 agents.py --backend ollama --model llama3.1:8b --only CP-0201 CP-0209   # quick test, 2 CPs
   python3 agents.py --backend ollama --model llama3.1:8b                          # all 36 CPs (about 1-2 hours on 16 GB)
   python3 evaluate.py
   ```
3. Commit `results/local/llama3.1-8b/runs.json` and `results/evaluation.json`. The results page shows a third column automatically.

Notes:
- The local run uses a 16k-token context window and temperature 0. If it is too slow, run fewer CPs with `--only` and say so in the results.
- "Trained on selected data" is not done here. This run uses the model as-is, with the contract and Demo 1's rule card in the prompt. A LoRA fine-tune on the labeled cases is the next step, and it needs a held-out set.

## Live demo on your laptop
```bash
ollama pull llama3.1:8b
python3 demo3/serve_local.py     # from the repo root
```
Open http://localhost:8000/clausestream/, then Sign in, pick a role, and click "Run agents live". It runs on Ollama with no key and no cost.
