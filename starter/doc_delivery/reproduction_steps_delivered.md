# Reproduction Steps

## Prerequisites

- **Python 3.11** (the pinned stack — `torch==2.5.1`, `torchvision==0.20.1`,
  `faiss-cpu==1.9.0`, `numpy==2.1.3` — all provide 3.11 wheels; the classroom uses
  3.12.13, which also works. Python 3.13/3.14 will **not** install torch 2.5.1.)
- ~2 GB free disk for the virtual environment (CPU-only torch).
- A valid, **active** Vocareum OpenAI API key for Steps 5–7 (embeddings + chat).
  Steps 1–4 and 8 need no API access.
- No GPU required; everything below was run CPU-only.

## Environment Setup

```bash
# From the repo root. Project files live under starter/.
python3.11 -m venv .venv            # Windows: py -3.11 -m venv .venv
source .venv/bin/activate           # Windows (PowerShell): .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r starter/requirements.txt

# Configure the RAG API credentials
cp starter/.env.example starter/rag_chatbot/.env
# then edit starter/rag_chatbot/.env:
#   OPENAI_API_KEY=<your active voc-... key>
#   OPENAI_BASE_URL=https://openai.vocareum.com/v1
```

**Local Windows notes (as actually run):** the venv was created outside OneDrive at
`C:\Users\tarie\venvs\nd909-c2` (a multi-GB torch venv should not sync to OneDrive —
sync can dehydrate a `.pyd`/`.dll` and break `import torch`). All Python commands
were run with `PYTHONUTF8=1` set, so that the given code's plain `open()` calls read
the UTF-8 Trivy report and policy docs correctly on Windows (which otherwise defaults
to cp1252). In PowerShell: `$env:PYTHONUTF8=1`.

## Step 1: Prepare Dataset

The balanced, pre-resized 256×256 dataset ships with the repo at
`classifier/balanced_data/` (1154 train + 390 test, 50/50 receipt / non_receipt), so
no preparation is required. To regenerate it from a raw unbalanced source:

```bash
cd starter/classifier
python data.py --source /path/to/raw/data --target balanced_data
```

## Step 2: Train and Evaluate Clean Model

The clean checkpoint is provided; just verify it:

```bash
cd starter/classifier
python evaluate.py --model-path checkpoints/receipt_cnn_clean.pt \
  --test-dir balanced_data/test \
  --results-dir ../attacks/results/02_label_flip/clean
```

Expected output: **Accuracy 0.9436**, Precision 0.9943, Recall 0.8923, F1 0.9405
(>94%), and a `metrics.json` + `confusion_matrix.png` written to the clean results dir.

## Step 3: FGSM Attack

```bash
cd starter/attacks
python 01_fgsm_evasion.py
```

Expected: a table sweeping ε ∈ {0.0, 0.01, 0.03, 0.05, 0.1, 0.15}; adversarial
accuracy falls from 0.9436 (ε=0) to ~0.27 (ε=0.10), attack success rate peaks ~0.71.
Writes `results/01_fgsm/fgsm_results.json` and one clean-vs-adversarial PNG per ε.
(Runtime ~7 min CPU: 390 images × 6 ε with per-image backprop.)

## Step 4: Data Poisoning

```bash
# 1. Create the poisoned training set (targeted; test set left clean). 10% flip,
#    non_receipt -> receipt (the direction that actually degrades the model).
cd starter/attacks
python 02_label_flip_poisoning.py --flip-rate 0.10 --target-class non_receipt

# 2. Retrain on the poisoned data (~20-40 min CPU, 15 epochs)
cd ../classifier
python train.py --data-dir poisoned_data --checkpoint-name receipt_cnn_poisoned.pt

# 3. Evaluate the poisoned model on the CLEAN test set
python evaluate.py --model-path checkpoints/receipt_cnn_poisoned.pt \
  --test-dir balanced_data/test \
  --results-dir ../attacks/results/02_label_flip/poisoned

# 4. (Baseline for comparison — already produced in Step 2)
python evaluate.py --model-path checkpoints/receipt_cnn_clean.pt \
  --test-dir balanced_data/test \
  --results-dir ../attacks/results/02_label_flip/clean
```

Expected: 115 labels flipped (10.0%, ≤10%), non_receipt→receipt; the poisoned model
scores **0.8077 accuracy vs. 0.9436 clean (−13.6 pp)** and receipt recall 0.62 vs 0.89
on the same clean test set. Exact figures are in `poisoning_results_delivered.md`.
(These flags are the script's defaults, so a bare `python 02_label_flip_poisoning.py`
reproduces the same attack; pass `--target-class both` for the weaker symmetric flip,
which barely moves accuracy on this well-separated task.)

## Step 5: RAG Chatbot Setup

```bash
cd starter/rag_chatbot
python build_index.py     # embeds 4 policy docs -> FAISS (needs an active API key)
python app.py             # starts Flask on http://localhost:5001
```

Expected: `Total chunks: ~23`, `FAISS index built: 23 vectors, dim=1536`. Sanity check
(in another shell):

```bash
curl -X POST http://localhost:5001/chat -H "Content-Type: application/json" \
  -d '{"question": "What is the meal expense limit?"}'
```

Expected: an answer citing **$75 per person per meal**.

## Step 6: Prompt Injection

```bash
cd starter/attacks
python 03_prompt_injection.py       # requires app.py running (Step 5)
```

Expected: 5 techniques executed; the transcript records `injection_successful` and
`confidential_source_disclosed` separately per attempt. Writes
`results/03_prompt_injection/prompt_injection_results.json`. See
`prompt_injection_transcript_delivered.md`.

## Step 7: Data Exfiltration

```bash
cd starter/attacks
python 04_data_exfiltration.py      # requires app.py running (Step 5)
```

Expected: 6 queries executed; the CONFIDENTIAL document appears in the retrieved
`sources` and/or confidential figures leak into the answer text. Writes
`results/04_exfiltration/data_exfiltration_results.json`. See
`data_exfiltration_evidence_delivered.md`.

## Step 8: Supply Chain Analysis

```bash
cd starter/attacks
python 05_supply_chain_analysis.py
```

Expected: 804 total CVEs (34 HIGH / 160 MEDIUM / 601 LOW / 9 UNKNOWN), 6 Dockerfile
issues, overall risk HIGH. Writes `results/05_supply_chain/supply_chain_report.json`.

## Expected Results Summary

| Attack | Metric | Expected Result |
|--------|--------|----------------|
| Clean baseline | Test accuracy | 0.9436 (P 0.9943 / R 0.8923 / F1 0.9405) |
| FGSM evasion | Adversarial accuracy vs. ε | 0.94 (ε=0) → 0.27 (ε=0.10); success rate ~0.71 |
| Label-flip poisoning | Accuracy drop on clean test set | 0.9436 → 0.8077 (−13.6 pp) at 10% targeted flip; recall 0.89 → 0.62 |
| Prompt injection | injection_successful / confidential_source_disclosed | ≥1 of 5 misbehaves and/or leaks a confidential source |
| Data exfiltration | Confidential retrieval | CONFIDENTIAL file in `sources` and/or leaked figures |
| Supply chain | Severity + Dockerfile issues | 804 CVEs (34 HIGH), 6 Dockerfile issues, risk HIGH |
