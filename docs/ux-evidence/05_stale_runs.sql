\echo '== Stale active runs by age, and whether a newer run for the same doc+task exists'
SELECT t.status, count(*) AS runs,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM task_runs n WHERE n.doc_id = t.doc_id AND n.task = t.task AND n.id > t.id AND n.status = 'completed')) AS superseded_by_completed,
       count(*) FILTER (WHERE t.updated_at::timestamptz < now() - interval '1 day') AS older_than_1d
FROM task_runs t
WHERE t.status IN ('running', 'retrying')
GROUP BY 1;
