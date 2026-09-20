# Executive Risk Summary

**Prepared for:** CISO and executive leadership, FinanceGuard Inc.
**Prepared by:** Tarie Nosworthy, AI Red Team · **Date:** 2026-09-20

## Overview

We tested FinanceGuard's two AI systems — the automated receipt classifier and the
expense-policy chatbot — plus their deployment setup, ahead of wider production use.
All five planned attacks succeeded to some degree. The most serious issue is that the
chatbot will hand confidential executive-compensation data to **any** employee who
asks in the right way; we also showed that the receipt classifier can be reliably
fooled or degraded, and that the container it all runs in is configured insecurely.
None of these require sophisticated tooling. We recommend remediation before broader
rollout.

## Risk Dashboard

| System | Risk Level | Key Finding |
|--------|-----------|-------------|
| Receipt Classifier | **HIGH** | Fooled by invisible image tweaks; and its accuracy can be quietly halved by tampering with training data. |
| RAG Chatbot | **CRITICAL** | Leaks confidential executive pay data to unauthenticated users; every probing query retrieved the restricted document. |
| Deployment Infrastructure | **HIGH** | Runs with maximum privileges (root), ships its own API key inside the image, and carries known unpatched vulnerabilities. |

## Findings Summary

### 1. Chatbot leaks confidential compensation data — CRITICAL

**Business Impact:** The restricted executive bonus/salary document is stored in the
same searchable knowledge base as public policies, with no access checks. In testing,
every one of six ordinary-sounding questions pulled that document, and most returned
actual figures — salary bands, bonus multipliers, the stock strike price, clawback
terms. Any employee (or anyone who reaches the chatbot) could harvest board-level
compensation data. This is a direct confidentiality breach with legal, HR, and morale
consequences, and it works even when the chatbot "refuses," because the data is fetched
before the refusal happens.

### 2. Receipt classifier can be evaded with invisible tampering — HIGH

**Business Impact:** By adding noise a human reviewer would not notice, an attacker can
make the system accept a non-receipt as a valid receipt (or reject a real one). Accuracy
dropped from 94% to 27% under attack. In an automated expense pipeline this enables
fraudulent reimbursements to sail through, or valid ones to be blocked.

### 3. Training-data tampering silently breaks the classifier — HIGH

**Business Impact:** Changing just 10% of training labels cut the model's accuracy from
94% to 81% and caused it to **reject roughly 4 in 10 genuine receipts** — while still
looking healthy on some metrics. An insider or a compromised data feed could degrade or
steer the system in a way that is hard to detect, driving reimbursement errors and
manual-review costs.

### 4. Chatbot instructions can be overridden — MEDIUM

**Business Impact:** Crafted input disguised as an official "policy update" made the
chatbot follow attacker instructions instead of its own. While its built-in safeguards
blocked most attempts, a determined user can still manipulate its responses — a risk of
misinformation (e.g., fake expense limits) and a stepping stone to the data leak above.

### 5. Insecure deployment container — HIGH

**Business Impact:** The application runs with full administrative privileges, and the
build copies its secret API key into the shipped image, so a single break-in escalates
to full control and a leaked credential (and its budget). The image also carries 34
high-severity known vulnerabilities (three immediately patchable) and leftover hacking-
useful tools. This turns any application-level flaw into a much larger breach.

## Prioritized Remediation

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| 1 | Remove the confidential compensation document from the shared chatbot index and require authentication + per-document access control on retrieval. | Low–Medium | Eliminates the CRITICAL data leak |
| 2 | Harden the container: run as a non-root user and stop copying the API key into the image (add an ignore-list); rotate the exposed key. | Low | Removes root-level blast radius and secret exposure |
| 3 | Patch the three fixable high-severity dependencies and pin the base image; adopt hash-verified installs. | Low | Closes known, exploitable supply-chain holes |
| 4 | Add defenses to the receipt classifier (adversarial training, input checks) and require human review for high-value auto-approvals. | Medium | Reduces evasion fraud risk |
| 5 | Lock down and monitor the training pipeline: data provenance, label auditing, per-class accuracy alerts across retrains. | Medium | Detects/prevents data poisoning |

## Conclusion

**Top recommendation: fix the chatbot data leak first (Priority 1).** It is the highest
impact, lowest effort item — confidential executive compensation is currently reachable
by any user through a normal-looking question, and the fix (segregate confidential
content and add access control) is straightforward. Pairing that with the container
hardening in Priority 2 removes the two issues most likely to cause an immediate,
reportable incident. The classifier and pipeline defenses (Priorities 4–5) are
important but can follow. We advise completing Priorities 1–3 before expanding these
systems into wider production.
