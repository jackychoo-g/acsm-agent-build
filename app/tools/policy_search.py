"""BigQuery VECTOR_SEARCH retrieval tool and restricted audit table lookup."""

from __future__ import annotations

import functools
from typing import Any

from google import genai
from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import bigquery
from google.genai import types

from app import config


@functools.cache
def _bq() -> bigquery.Client:
    # Jobs run in the runtime project; table names are fully qualified so data
    # can live in a separate project (`config.DATA_PROJECT`).
    return bigquery.Client(project=config.RUNTIME_PROJECT, location=config.REGION)


@functools.cache
def _genai() -> genai.Client:
    return genai.Client(vertexai=True, project=config.RUNTIME_PROJECT, location=config.REGION)


@functools.cache
def _has_page_column() -> bool:
    # A `page` column is written by the ingestion job from the PDF text layer.
    # Without it we omit the #page anchor rather than guess one: a wrong page
    # sends the reader to the wrong clause, which is worse than no anchor.
    try:
        return any(f.name == "page" for f in _bq().get_table(config.CHUNKS_TABLE).schema)
    except (Forbidden, NotFound):
        return False


def _attach_citation(row: dict[str, Any]) -> dict[str, Any]:
    file_path = row.get("file_path", "")
    page = row.get("page")
    base_url = f"https://storage.cloud.google.com/{config.RAG_BUCKET}/raw/{file_path}"
    is_pdf = file_path.endswith(".pdf")
    anchor = f"#page={page}" if is_pdf and page else ""
    row["source_url"] = base_url + anchor
    row["gcs_uri"] = f"gs://{config.RAG_BUCKET}/raw/{file_path}"
    page_label = f", p.{page}" if is_pdf and page else ""
    row["citation_markdown"] = (
        f"[{row.get('doc_id', '')}: {row.get('title', '')} "
        f"(v{row.get('version', '')}, eff. {row.get('effective_date', '')}), "
        f"Clause {row.get('clause_id', '')} — {row.get('heading', '')}{page_label}]"
        f"({row['source_url']})"
    )
    return row


def search_policy_corpus(
    query: str,
    include_internal: bool = True,
    top_k: int = 5,
) -> dict[str, Any]:
    """Search the AEON Credit policy, product, circular, and FAQ knowledge base in BigQuery.

    Always call this tool before answering questions about underwriting rules
    (DSR, NDI, CTOS, delinquency, credit limits), product disclosures, fees,
    SOPs, or branch circulars. Returns matching clauses with their document ID,
    version, effective_date, access classification, and clickable `source_url` /
    `citation_markdown` links.

    Args:
        query: Natural-language search question (English or Bahasa Malaysia).
        include_internal: Set True for internal staff/underwriters; set False
            to restrict retrieval to public customer-facing documents only.
        top_k: Number of top matching chunks to retrieve (default 5, max 10).
    """
    # TODO(Task 1): Implement BigQuery VECTOR_SEARCH retrieval per SPEC.md:
    # 1. Clamp top_k to [1, 10].
    # 2. Embed `query` with `_genai().models.embed_content` using `config.EMBED_MODEL`,
    #    `task_type="RETRIEVAL_QUERY"`, and `output_dimensionality=config.EMBED_DIM`.
    # 3. Query `VECTOR_SEARCH` on `config.CHUNKS_TABLE` (filtering `WHERE access = 'public'`
    #    when `include_internal` is False) with `distance_type => 'COSINE'` and
    #    `options => '{"use_brute_force": true}'`, ordered by `distance ASC`.
    # 4. Pass each row through `_attach_citation(dict(r.items()))` and return:
    #    {"backend": "bigquery_vector_search", "table": config.CHUNKS_TABLE,
    #     "query": query, "include_internal": include_internal,
    #     "match_count": len(rows), "matches": rows}
    raise NotImplementedError("Task 1: implement search_policy_corpus per SPEC.md")


def lookup_restricted_audit_log(branch: str = "") -> dict[str, Any]:
    """Query the restricted branch credit exception audit log in BigQuery.

    Access depends on the identity the agent runs as. The shared workshop
    service account is denied on purpose; an agent deployed with its own Agent
    Identity can be granted access. Report the returned `status` to the user.

    Args:
        branch: Optional branch name filter (e.g. 'Johor Bahru', 'Penang').
    """
    where = "WHERE LOWER(branch) LIKE LOWER(@branch)" if branch else ""
    sql = f"""
    SELECT audit_id, branch, product, finding, CAST(audit_date AS STRING) AS audit_date
    FROM `{config.AUDIT_TABLE}`
    {where}
    ORDER BY audit_date DESC
    """
    params = [bigquery.ScalarQueryParameter("branch", "STRING", f"%{branch}%")] if branch else []
    try:
        job = _bq().query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
        rows = [dict(r.items()) for r in job.result()]
    except Forbidden as exc:
        # Returned, not raised: an uncaught exception aborts the ADK run and the
        # user sees an empty reply. The denial itself is the lesson here.
        return {
            "status": "PERMISSION_DENIED",
            "table": config.AUDIT_TABLE,
            "error": exc.message,
            "explanation": (
                "This agent's runtime identity has no read access to the audit table. "
                "Access is granted per identity in BigQuery IAM, not by the agent code."
            ),
        }
    return {"status": "OK", "table": config.AUDIT_TABLE, "row_count": len(rows), "rows": rows}
