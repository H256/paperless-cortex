-- UX evidence: speed before/after the 2026-10-11 review features, and blind-check sample ids.

\echo '== 1. Seconds per doc in multi-doc sessions, before and after 2026-10-11'
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
    SELECT session_id, min(at) AS started, extract(epoch FROM max(at) - min(at)) AS seconds, count(DISTINCT doc_id) AS docs
    FROM sess GROUP BY session_id
)
SELECT CASE WHEN started >= '2026-10-11' THEN 'after' ELSE 'before' END AS period,
       count(*) AS sessions, sum(docs) AS docs,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds / docs)::numeric, 1) AS p50_sec_per_doc,
       round((sum(seconds) / sum(docs))::numeric, 1) AS weighted_sec_per_doc
FROM agg WHERE docs >= 2 GROUP BY 1 ORDER BY 1;

\echo '== 2. Correction rate before and after 2026-10-11 (by first apply)'
WITH r AS (
    SELECT doc_id, min(created_at::timestamptz) AS first_at FROM suggestion_audit
    WHERE action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback' GROUP BY doc_id
), t AS (
    SELECT doc_id, bool_or(action = 'field_override' OR action LIKE 'field_variants:%') AS corrected
    FROM suggestion_audit GROUP BY doc_id
)
SELECT CASE WHEN first_at >= '2026-10-11' THEN 'after' ELSE 'before' END AS period,
       count(*) AS docs, count(*) FILTER (WHERE corrected) AS corrected,
       round(100.0 * count(*) FILTER (WHERE corrected) / count(*), 1) AS pct
FROM r JOIN t USING (doc_id) GROUP BY 1 ORDER BY 1;

\echo '== 3. Blind-check sample: 40 accepted-as-is and 20 corrected docs (fixed seed)'
SELECT setseed(0.42);
WITH r AS (
    SELECT doc_id, bool_or(action = 'field_override' OR action LIKE 'field_variants:%') AS corrected,
           bool_or(action LIKE 'apply_to_document:%' AND action <> 'apply_to_document:writeback') AS applied
    FROM suggestion_audit GROUP BY doc_id
), ranked AS (
    SELECT doc_id, corrected, row_number() OVER (PARTITION BY corrected ORDER BY doc_id::text, random()) AS unused, random() AS shuffle
    FROM r WHERE applied
), picked AS (
    SELECT doc_id, corrected, row_number() OVER (PARTITION BY corrected ORDER BY shuffle) AS n FROM ranked
)
SELECT string_agg(doc_id::text, ',' ORDER BY n) FILTER (WHERE NOT corrected AND n <= 40) AS accepted_as_is_ids,
       string_agg(doc_id::text, ',' ORDER BY n) FILTER (WHERE corrected AND n <= 20) AS corrected_ids
FROM picked;
