-- UX evidence: aggregate funnel from suggestion_audit, document_suggestions and task_runs.
-- PostgreSQL. Read-only; returns counts and durations, no document content.
-- Run: psql "$DSN" -f docs/ux-evidence/01_funnel.sql
BEGIN TRANSACTION READ ONLY;

\echo '== 1. Data range and volume per audit action family'
SELECT split_part(action, ':', 1) AS action_family,
       count(*) AS events,
       count(DISTINCT doc_id) AS docs,
       min(created_at) AS first_at,
       max(created_at) AS last_at
FROM suggestion_audit
GROUP BY 1
ORDER BY events DESC;

\echo '== 2. Funnel: documents -> suggestion -> reviewed'
SELECT (SELECT count(*) FROM documents) AS docs_total,
       (SELECT count(DISTINCT doc_id) FROM document_suggestions) AS docs_with_suggestion,
       (SELECT count(DISTINCT doc_id) FROM suggestion_audit
         WHERE action LIKE 'apply_to_document:%' OR action = 'field_override') AS docs_with_user_change,
       (SELECT count(DISTINCT doc_id) FROM suggestion_audit
         WHERE action = 'apply_to_document:writeback') AS docs_written_back;

\echo '== 3. Applied fields per source'
SELECT source, split_part(action, ':', 2) AS field, count(*) AS applies
FROM suggestion_audit
WHERE action LIKE 'apply_to_document:%'
GROUP BY 1, 2
ORDER BY applies DESC;

\echo '== 4. Regeneration and manual override per field (signal for distrust)'
SELECT coalesce(field, split_part(action, ':', 2)) AS field,
       count(*) FILTER (WHERE action LIKE 'field_variants:%') AS regenerations,
       count(*) FILTER (WHERE action = 'field_override') AS overrides
FROM suggestion_audit
WHERE action LIKE 'field_variants:%' OR action = 'field_override'
GROUP BY 1
ORDER BY overrides DESC;

\echo '== 5. Suggestion -> first apply latency, and time spent per review session'
WITH first_apply AS (
    SELECT doc_id, min(created_at::timestamptz) AS applied_at
    FROM suggestion_audit
    WHERE action LIKE 'apply_to_document:%'
    GROUP BY doc_id
), first_suggestion AS (
    SELECT doc_id, min(processed_at::timestamptz) AS suggested_at
    FROM document_suggestions
    GROUP BY doc_id
), gaps AS (
    SELECT created_at::timestamptz
             - lag(created_at::timestamptz) OVER (ORDER BY created_at::timestamptz) AS gap
    FROM suggestion_audit
    WHERE action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback'
)
SELECT (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY a.applied_at - s.suggested_at)
          FROM first_apply a JOIN first_suggestion s USING (doc_id)
         WHERE a.applied_at >= s.suggested_at) AS median_suggest_to_apply,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY gap)
          FROM gaps WHERE gap < interval '10 minutes') AS median_gap_between_applies_in_session;

\echo '== 6. Task failures and retries visible to users'
SELECT task, status, count(*) AS runs,
       round(avg(attempt), 2) AS avg_attempt,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms) AS p50_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
FROM task_runs
GROUP BY 1, 2
ORDER BY task, runs DESC;

\echo '== 7. Most frequent error types'
SELECT task, error_type, count(*) AS runs
FROM task_runs
WHERE error_type IS NOT NULL
GROUP BY 1, 2
ORDER BY runs DESC
LIMIT 20;

ROLLBACK;
