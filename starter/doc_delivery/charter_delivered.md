# Red Team Charter

## Engagement Details

| Field | Value |
|-------|-------|
| **Engagement Name** | FinanceGuard AI Red Team Assessment — Receipt Classifier & Expense-Policy RAG |
| **Date** | 2026-09-19 – 2026-09-20 (execution and reporting) |
| **Assessor** | Tarie Nosworthy — Junior AI Red Team Operator |
| **Sponsor** | Chief Information Security Officer (CISO), FinanceGuard Inc. |

## Objectives

Execute five adversarial attacks across FinanceGuard's two AI systems and their
deployment pipeline, and document the security posture of each before wider
production rollout.

1. **FGSM Evasion (Receipt Classifier).** Demonstrate that gradient-based, near-
   imperceptible perturbations to an uploaded image can flip the classifier's
   decision, letting non-receipts be processed as valid expenses (or vice versa).
2. **Label-Flip Data Poisoning (Training Pipeline).** Show that corrupting a small
   fraction (≤10%) of training labels measurably degrades model accuracy on a
   clean, untouched test set — a stealthy integrity attack on the ML supply chain.
3. **Prompt Injection (RAG Chatbot).** Show that crafted user input can override
   the assistant's system instructions — extracting the system prompt, hijacking
   its role, contradicting policy, or bypassing filters via encoding.
4. **Data Exfiltration (RAG Vector Store).** Demonstrate that a document marked
   CONFIDENTIAL, indexed in the same FAISS store as public policy, can be retrieved
   by semantically similar queries because the store enforces no access control.
5. **Supply Chain Analysis (Docker / Dependencies).** Identify OS- and Python-
   package CVEs from a Trivy scan and configuration weaknesses in the Dockerfile
   that expose the deployment pipeline.

## Scope

### In Scope
- **Receipt Classifier** (`classifier/`): the pre-trained `receipt_cnn_clean.pt`
  checkpoint, the `ReceiptCNN` architecture, the balanced dataset, and the
  training pipeline (`train.py`, `data.py`).
- **Expense-Policy RAG Chatbot** (`rag_chatbot/`): the Flask `/chat` API, the RAG
  pipeline (`rag.py`), the FAISS index, and the four indexed policy documents,
  including `executive_bonus_structure_CONFIDENTIAL.md`.
- **Deployment infrastructure**: the provided `Dockerfile` and the Trivy scan
  report `06_trivy_report.json`.

### Out of Scope
- FinanceGuard production systems, real employee/customer/PII data, and any live
  compensation records. All work uses the provided synthetic assets only.
- The upstream OpenAI/Vocareum service, its models, and its infrastructure. Only
  the application's *use* of the API is assessed, not the provider.
- Denial-of-service, load/stress testing, and any attack whose purpose is to
  disrupt availability.
- Modification of the provided infrastructure code. Attacks are additive
  (implemented in `attacks/`); given files are treated as the system under test.
- Networked, third-party, or physical targets not part of this repository.

## Rules of Engagement

1. **Isolated environment only.** All attacks run locally against the provided
   copies. No production system is touched and no real data is exposed.
2. **No destructive or persistent changes to the system under test.** The clean
   checkpoint and the `balanced_data/test/` set are never modified; poisoning
   operates on a *copy* (`poisoned_data/`) so results are reproducible and the
   baseline is preserved.
3. **Authorized, time-boxed, and documented.** Testing is performed under the
   CISO's written authorization; every finding is logged with reproduction steps.
4. **Confidential data handled as evidence, not exposed.** Any confidential
   content retrieved during exfiltration testing is recorded only as proof of the
   vulnerability and is not redistributed beyond this report.
5. **Responsible disclosure.** Findings and remediation are delivered to the
   sponsor; no vulnerability is disclosed externally.

## Success Criteria

| Attack Vector | Success Metric |
|---------------|---------------|
| FGSM Evasion | Adversarial accuracy degrades sharply as ε grows across ≥3 ε values — falling below 50% at a small, near-imperceptible ε — demonstrating clear progressive degradation of the classifier. |
| Label-Flip Poisoning | Flip rate ≤10% of training labels; poisoned model shows ≥5 percentage-point accuracy drop vs. the clean baseline on the *same clean* test set. |
| Prompt Injection | ≥5 distinct techniques executed; at least one causes the assistant to misbehave (`injection_successful`) and/or surfaces a confidential source (`confidential_source_disclosed`), each tracked separately. |
| Data Exfiltration | ≥5 distinct queries; confidential data is proven leaked either in answer text or by the CONFIDENTIAL file appearing in the retrieved `sources`. |
| Supply Chain Analysis | Trivy CVEs categorized by severity; specific HIGH CVEs with fixes identified; ≥3 Dockerfile issues found, each with a concrete remediation. |

## Deliverables

- **Five attack scripts** (`attacks/01_fgsm_evasion.py` … `05_supply_chain_analysis.py`),
  runnable with default arguments, each emitting printed results and/or JSON.
- **Attack output artifacts** (`attacks/results/…`): FGSM JSON + per-ε PNGs,
  label-flip evidence PNG + poisoned-model metrics, prompt-injection and
  exfiltration transcripts (JSON), and the supply-chain report JSON.
- **Nine documentation files** in `doc_delivery/`: this Charter, the Vulnerability
  Log, the four per-attack results/evidence documents (FGSM, poisoning, prompt
  injection, exfiltration), the Supply Chain Analysis, the Executive Risk Summary,
  and the Reproduction Steps.
