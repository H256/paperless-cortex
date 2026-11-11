-- UX evidence: how review work actually happens over time. Counts and durations only.
-- "Session" = applies/overrides/regenerations with gaps below 30 minutes.

\echo '== 1. Documents reviewed per month (first field apply), and fields per doc'
WITH per_doc AS (
    SELECT doc_id, min(created_at::timestamptz) AS first_at, count(*) AS applies
    FROM suggestion_audit
    WHERE action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback'
    GROUP BY doc_id
)
SELECT to_char(first_at, 'YYYY-MM') AS month, count(*) AS docs, round(avg(applies), 1) AS avg_field_applies
FROM per_doc GROUP BY 1 ORDER BY 1;

\echo '== 2. Review sessions: length, docs and seconds per doc'
WITH ev AS (
    SELECT doc_id, created_at::timestamptz AS at
    FROM suggestion_audit
    WHERE action = 'field_override' OR action LIKE 'field_variants:%'
       OR (action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback')
), marked AS (
    SELECT *, CASE WHEN at - lag(at) OVER (ORDER BY at) < interval '30 minutes' THEN 0 ELSE 1 END AS new_session
    FROM ev
), sess AS (
    SELECT *, sum(new_session) OVER (ORDER BY at) AS session_id FROM marked
), agg AS (
    SELECT session_id, min(at) AS started, extract(epoch FROM max(at) - min(at)) AS seconds,
           count(DISTINCT doc_id) AS docs, count(*) AS events
    FROM sess GROUP BY session_id
)
SELECT count(*) AS sessions,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY docs) AS p50_docs,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY docs) AS p90_docs,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds)::numeric / 60, 1) AS p50_minutes,
       round((sum(seconds) FILTER (WHERE docs >= 2) / nullif(sum(docs) FILTER (WHERE docs >= 2), 0))::numeric, 1) AS sec_per_doc_multi_doc_sessions,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds / docs)
             FILTER (WHERE docs >= 2)::numeric, 1) AS p50_sec_per_doc
FROM agg;

\echo '== 3. Share of reviewed docs that needed correction'
WITH reviewed AS (
    SELECT DISTINCT doc_id FROM suggestion_audit
    WHERE action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback'
), touched AS (
    SELECT doc_id,
           bool_or(action = 'field_override') AS has_override,
           bool_or(action LIKE 'field_variants:%') AS has_regen
    FROM suggestion_audit GROUP BY doc_id
)
SELECT count(*) AS reviewed_docs,
       count(*) FILTER (WHERE has_override) AS with_override,
       count(*) FILTER (WHERE has_regen) AS with_regeneration,
       count(*) FILTER (WHERE NOT has_override AND NOT has_regen) AS accepted_as_is
FROM reviewed JOIN touched USING (doc_id);

\echo '== 4. Fields applied per reviewed doc (distinct fields)'
WITH f AS (
    SELECT doc_id, count(DISTINCT split_part(action, ':', 2)) AS fields
    FROM suggestion_audit
    WHERE action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback'
    GROUP BY doc_id
)
SELECT fields, count(*) AS docs FROM f GROUP BY 1 ORDER BY 1;

\echo '== 5. Coverage per field among reviewed docs'
SELECT split_part(action, ':', 2) AS field, count(DISTINCT doc_id) AS docs
FROM suggestion_audit
WHERE action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback'
GROUP BY 1 ORDER BY 2 DESC;

\echo '== 6. Task failures per month for the noisy and user-facing tasks'
SELECT to_char(created_at::timestamptz, 'YYYY-MM') AS month, task, count(*) AS failed
FROM task_runs
WHERE status = 'failed' AND task IN ('similarity_index', 'suggestions_vision', 'suggestions_paperless', 'vision_ocr')
GROUP BY 1, 2 ORDER BY 1, 2;

\echo '== 7. Unfinished runs currently stuck'
SELECT task, status, count(*) AS runs, min(updated_at) AS oldest_update
FROM task_runs
WHERE status IN ('running', 'retrying', 'pending', 'queued')
GROUP BY 1, 2 ORDER BY 3 DESC;

\echo '== 8. Writeback jobs'
SELECT status, dry_run, count(*) AS jobs, sum(docs_changed) AS docs_changed, max(created_at) AS last_at
FROM writeback_jobs GROUP BY 1, 2 ORDER BY jobs DESC;
