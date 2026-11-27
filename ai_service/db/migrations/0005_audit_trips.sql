-- 0005: tokens per model call ("trip"), to see where a question's tokens go.
--   trips: one JSON object per call to a model, in order, e.g.
--          {"trip": 1, "purpose": "plan", "provider": "groq", "in": 2400, "out": 90,
--           "ms": 850, "ok": true}
--          A failed call has "ok": false and the HTTP status, and no tokens.
--          Labels and counts only: never the question, arguments or figures.
ALTER TABLE ai.audit_log
    ADD COLUMN trips jsonb NOT NULL DEFAULT '[]'::jsonb;
