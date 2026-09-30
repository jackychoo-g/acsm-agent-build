# SPEC.md — ACSM Underwriting & Policy Agent Build Specification

You are building an ADK agent for AEON Credit Service (M) Berhad (`acsm-agent-build`) deployed to **Agent Runtime on Gemini Enterprise Agent Platform**.

## Fixed Platform Contract (Do Not Change)

- **Models**: `gemini-3.8-flash` (`config.MODEL`) for generation; `gemini-embedding-001` (`config.EMBED_MODEL`, 768 dimensions `config.EMBED_DIM`) for embeddings. Never reference older or deprecated model versions.
- **Region**: `asia-southeast1` (`config.REGION`) for Agent Runtime, BigQuery, RAG Engine and Model Armor. Model calls use `GOOGLE_CLOUD_LOCATION=global`.
- **Shared Runtime Service Account**: Every participant deploys with the shared service account `acsm-lab-agent@<project>.iam.gserviceaccount.com` (`--service-account` in `Makefile`). Never pass `--agent-identity`, never run Terraform, and never modify IAM.
- **Per-Participant Agent Name**: Every deployed agent is named `acsm-agent-<owner>` via `make deploy OWNER=<participant-name>`. Before running `make deploy`, always ask the participant for their name if they have not provided `OWNER=<name>`.
- **Configuration**: All environment settings come from `app/config.py` (loaded from `.lab.env` via `make configure`). Never hardcode project IDs, bucket names, or Cloud Storage URLs.

---

## Task 1: BigQuery Vector Search Retrieval Tool with Clickable Citations

### Files to Edit
1. `app/tools/policy_search.py` — implement `search_policy_corpus(query: str, include_internal: bool = True, top_k: int = 5) -> dict[str, Any]`
2. `app/agent.py` — add `search_policy_corpus` to the `tools=[...]` list in `create_bq_rag_agent`

### Requirements
In `app/tools/policy_search.py`, replace `raise NotImplementedError(...)` inside `search_policy_corpus` with:

1. Clamp `top_k`:
   ```python
   top_k = max(1, min(int(top_k), 10))
   ```
2. Generate the 768-dimensional query embedding using `_genai().models.embed_content`:
   ```python
   emb = _genai().models.embed_content(
       model=config.EMBED_MODEL,
       contents=[query],
       config=types.EmbedContentConfig(
           task_type="RETRIEVAL_QUERY",
           output_dimensionality=config.EMBED_DIM,
       ),
   )
   query_vec = list(emb.embeddings[0].values)
   ```
3. Query `VECTOR_SEARCH` on `config.CHUNKS_TABLE` via `_bq().query(sql, job_config=job_cfg)`:
   - Filter `WHERE access = 'public'` when `include_internal` is `False` (`access_filter = "" if include_internal else "WHERE access = 'public'"`).
   - Include `base.page,` only when `_has_page_column()` is `True` (`page_col = "base.page," if _has_page_column() else ""`).
   - Exact SQL query:
     ```python
     sql = f"""
     SELECT
       base.chunk_id, base.doc_id, base.family, base.title, base.version,
       CAST(base.effective_date AS STRING) AS effective_date,
       base.language, base.access, base.format, base.file_path,
       base.clause_id, base.heading, base.chunk_text, {page_col}
       ROUND(distance, 4) AS cosine_distance
     FROM VECTOR_SEARCH(
       (SELECT * FROM `{config.CHUNKS_TABLE}` {access_filter}),
       'embedding',
       (SELECT @qvec AS query_embedding),
       top_k => {top_k},
       distance_type => 'COSINE',
       options => '{{"use_brute_force": true}}'
     )
     ORDER BY distance ASC
     """
     job_cfg = bigquery.QueryJobConfig(
         query_parameters=[bigquery.ArrayQueryParameter("qvec", "FLOAT64", query_vec)]
     )
     ```
4. Attach citations to each row with the existing `_attach_citation` helper and return the contract dictionary:
   ```python
   rows = [_attach_citation(dict(r.items())) for r in _bq().query(sql, job_config=job_cfg).result()]
   return {
       "backend": "bigquery_vector_search",
       "table": config.CHUNKS_TABLE,
       "query": query,
       "include_internal": include_internal,
       "match_count": len(rows),
       "matches": rows,
   }
   ```
5. In `app/agent.py`, include `search_policy_corpus` inside `tools=[...]` in `create_bq_rag_agent`.

### Acceptance Check
```bash
make check-task1
```

---

## Task 2: Sessions & Memory Bank Recall

### File to Edit
`app/agent.py`

### Requirements
1. Implement `_persist_session_to_memory(callback_context: CallbackContext) -> None` so that at the end of every agent turn it extracts session facts into Memory Bank:
   ```python
   async def _persist_session_to_memory(callback_context: CallbackContext) -> None:
       """Trigger Memory Bank extraction at the end of each agent turn."""
       try:
           await callback_context.add_session_to_memory()
       except Exception as exc:
           logger.debug("Memory persistence skipped: %s", exc)
   ```
2. In both `create_bq_rag_agent` and `create_rag_engine_agent`:
   - Add `preload_memory` to `tools=[...]`.
   - Set `after_agent_callback=_persist_session_to_memory`.

### Acceptance Check
```bash
make check-task2
```

---

## Task 3: Governance Guardrails (PDPA MyKad NRIC & Model Armor)

### File to Edit
`app/agent.py` (the callback implementation in `app/governance/policy_guard.py` is already provided).

### Requirements
In `_build_audit_subagent`, `create_bq_rag_agent`, and `create_rag_engine_agent` in `app/agent.py`, replace `before_model_callback=None` and `before_tool_callback=None` with:
```python
before_model_callback=before_model_governance_guard,
before_tool_callback=before_tool_governance_guard,
```

### Acceptance Check
```bash
make check-task3
```

---

## Task 4: Add a Golden Evaluation Case

### File to Edit
`tests/eval/datasets/acsm_golden.json`

### Requirements
`tests/eval/datasets/acsm_golden.json` starts with 3 evaluation cases (`ndi_superseded_v1_vs_v2`, `late_fee_schedule_conflict`, `platinum_fee_waiver_table`). Append at least **1 new evaluation case** to the `"eval_cases"` array (so there are at least 4 cases total) following the exact schema:

```json
    {
      "eval_case_id": "bahasa_malaysia_dsr_limit",
      "prompt": {
        "role": "user",
        "parts": [
          {
            "text": "Berapakah had maksimum DSR untuk pemohon bergaji RM 4,500 sebulan?"
          }
        ]
      },
      "reference": {
        "response": {
          "role": "model",
          "parts": [
            {
              "text": "Berdasarkan Polisi Pengunderaitan Kredit v2 (POL-CR-001-v2, berkuat kuasa 2026-01-01, Seksyen 2.0) dan Soalan Lazim Kad Kredit (FAQ-CARD-MS, Klausa Q7), had maksimum Nisbah Khidmat Hutang (DSR) bagi pemohon dengan pendapatan kasar RM 4,500 sebulan (RM 3,000 dan ke atas) ialah 70% (manakala pendapatan di bawah RM 3,000 dihadkan kepada 60%)."
            }
          ]
        }
      }
    }
```

### Acceptance Check
```bash
make check-task4
make verify
```

---

## Task 5: Deploy to Agent Runtime & Verify

1. **Ask the participant for their name** if they have not already given `OWNER=<name>`.
2. Run the full verification gate:
   ```bash
   make verify
   ```
3. Deploy the participant's agent to Agent Runtime using the shared service account:
   ```bash
   make deploy OWNER=<participant-name>
   ```
4. Test the deployed agent:
   ```bash
   make chat Q="What is the minimum NDI floor for an applicant with 3 dependants? Cite the source."
   make chat-audit
   make status
   ```
