# ACSM Agent Build Workshop (Vibe Coding with Antigravity + ADK + agents-cli)

Build and deploy an enterprise underwriting & policy agent for AEON Credit Service (M) Berhad on **Gemini Enterprise Agent Platform (Agent Runtime)** using Google ADK, `agents-cli`, and Antigravity.

If Antigravity is unavailable on your machine, use the full-code companion repository [`acsm-agent-workshop`](https://github.com/jackychoo-g/acsm-agent-workshop).

---

## 1. Authenticate `gcloud` (Two Credentials, plus the Runtime Identity)

Google Cloud separates CLI commands from Python SDK calls. Pass `--update-adc` to authenticate both credentials in a single sign-in:

```bash
gcloud auth login --update-adc --no-launch-browser
gcloud config set project <workshop-project-id>
```

| Credential | Command | What uses it |
|---|---|---|
| **1. CLI Credential** | `gcloud auth login` | `gcloud` CLI commands and `make configure` (reading Secret Manager) |
| **2. Application Default Credentials (ADC)** | `--update-adc` (or `gcloud auth application-default login`) | Local Python SDK calls (`google-cloud-bigquery`, `google-genai`), contract tests, and `agents-cli deploy` |
| **3. Shared Agent Runtime Identity** | `--service-account acsm-lab-agent@<project>.iam.gserviceaccount.com` | Your deployed agent in Agent Runtime. It can read `acsm_rag.policy_chunks` but is denied `acsm_rag.collections_internal_audit` |

---

## 2. Clone & Bootstrap

```bash
git clone https://github.com/jackychoo-g/acsm-agent-build.git
cd acsm-agent-build
make bootstrap    # installs uv, agents-cli 1.7.0, Python deps, and links agents-cli skills for Antigravity
make configure    # pulls shared workshop config from Secret Manager into .lab.env
make whoami       # verifies gcloud account, ADC token, project, and shared service account
```

Open the folder in Visual Studio Code with the **Google Antigravity** extension installed (or run the Antigravity CLI `agy` in your terminal). Both [`AGENTS.md`](AGENTS.md), [`SPEC.md`](SPEC.md), and `.agents/skills/google-agents-cli-*` are pre-loaded in this repo.

---

## 3. Build the Agent with Antigravity (4 Prompts)

Paste each prompt into Antigravity in order. Antigravity reads `SPEC.md` and `AGENTS.md`, edits the target files, and runs the acceptance check for that task.

### Prompt 1 — BigQuery Vector Search RAG Tool & Citation Contract
```text
Read SPEC.md and complete Task 1: implement search_policy_corpus in app/tools/policy_search.py using BigQuery VECTOR_SEARCH and _attach_citation, wire search_policy_corpus into create_bq_rag_agent in app/agent.py, and run `make check-task1` to verify it passes.
```

### Prompt 2 — Sessions & Memory Bank Recall
```text
Read SPEC.md and complete Task 2: implement _persist_session_to_memory in app/agent.py, add preload_memory and after_agent_callback=_persist_session_to_memory to both create_bq_rag_agent and create_rag_engine_agent, and run `make check-task2` to verify it passes.
```

### Prompt 3 — Governance Guardrails (PDPA MyKad NRIC & Model Armor)
```text
Read SPEC.md and complete Task 3: attach before_model_governance_guard and before_tool_governance_guard to _build_audit_subagent, create_bq_rag_agent, and create_rag_engine_agent in app/agent.py, and run `make check-task3` to verify it passes.
```

### Prompt 4 — Golden Evaluation Dataset & Contract Verification
```text
Read SPEC.md and complete Task 4: add the bahasa_malaysia_dsr_limit evaluation case to tests/eval/datasets/acsm_golden.json, then run `make check-task4` and `make verify` to confirm all contract and task checks pass.
```

---

## 4. Deploy Your Agent to Agent Runtime

Ask Antigravity to deploy your agent:

### Prompt 5 — Deploy to Agent Runtime
```text
Deploy my agent to Agent Runtime following AGENTS.md.
```

Per the rule in [`AGENTS.md`](AGENTS.md) (and enforced by `Makefile`), Antigravity will ask for your name first and run:

```bash
make deploy OWNER=<your-name>
```

This deploys `acsm-agent-<your-name>` to Agent Runtime in `asia-southeast1` using the shared service account `acsm-lab-agent@<project>.iam.gserviceaccount.com` (~4 minutes).

---

## 5. Test & Inspect Your Deployed Agent

```bash
make chat Q="What is the minimum NDI floor for an applicant with 3 dependants? Cite the source."
make chat Q="Berapakah had maksimum DSR untuk pemohon bergaji RM 4,500 sebulan?"
make chat-audit          # tests table-level IAM boundary -> returns PERMISSION_DENIED with explanation
make status OWNER=<your-name>
make trace
make audit-logs OWNER=<your-name>
make test-governance
```

When finished:
```bash
make cleanup OWNER=<your-name> CONFIRM=yes
```
