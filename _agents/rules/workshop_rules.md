# AGENTS.md

Instructions for any coding agent (Antigravity VS Code extension, Antigravity 2.0, Antigravity CLI `agy`, Gemini Code Assist, Gemini CLI) working in this repository.

## Mandatory Pre-Deployment Rule (Ask Participant Name First)

1. **Ask for the participant's name before deploying.** If the user asks you to deploy the agent and has not explicitly given their name (e.g. `OWNER=aisyah`), stop and ask them for their name first. Never guess the name from `gcloud config get-value account` or OS username.
2. **Deploy only via `make deploy OWNER=<participant-name>`.** That sets `--service-name acsm-agent-<owner>` and `--service-account acsm-lab-agent@<project>.iam.gserviceaccount.com`. Never run `agents-cli deploy` directly without those flags, and never pass `--agent-identity`.
3. Before or after deploying, run `make whoami OWNER=<participant-name>` so the participant sees their resolved agent name `acsm-agent-<owner>`.

## Build Workflow (`SPEC.md`)

Always read [`SPEC.md`](SPEC.md) first and implement the tasks in order, running the acceptance command after each task:

- **Task 1 (BigQuery RAG tool + citation contract)**: edit `app/tools/policy_search.py` and `app/agent.py`, then run `make check-task1`.
- **Task 2 (Sessions & Memory Bank recall)**: edit `app/agent.py`, then run `make check-task2`.
- **Task 3 (Governance callbacks: PDPA MyKad + Model Armor)**: edit `app/agent.py`, then run `make check-task3`.
- **Task 4 (Golden evaluation case)**: edit `tests/eval/datasets/acsm_golden.json`, then run `make check-task4` and `make verify`.

## Hard Guardrails

- **No IAM or Terraform**: Never run `terraform`, `gcloud projects add-iam-policy-binding`, `gcloud iam`, or any command that mutates project IAM, APIs, or org policies.
- **No Touching Other Participants' Agents**: Only interact with `acsm-agent-<this-participant>`.
- **Models**: Use only `gemini-3.8-flash` (`config.MODEL`) and `gemini-embedding-001` (`config.EMBED_MODEL`). Never introduce older or deprecated model versions.
- **Region**: Keep `asia-southeast1` (`config.REGION`).
- **No Hardcoded IDs**: Read project, bucket, dataset, and corpus from `app/config.py` (populated by `.lab.env` via `make configure`).
- **Preserve Audit Denial Contract**: `lookup_restricted_audit_log` must catch `Forbidden` and return `{"status": "PERMISSION_DENIED", ...}` rather than raising.
