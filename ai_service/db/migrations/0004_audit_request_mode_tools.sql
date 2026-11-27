-- 0004: link audit rows to application logs, and record "my data" requests.
--   request_id: the X-Request-ID also written on every log line for that request.
--               Logs carry no user identity; this table (tighter access) does.
--   mode:       'help' (help articles and finance notes) or 'my_data' (the user's own
--               PPA data through read-only tools).
--   tools:      names of the tools the model called (never their arguments or results).
ALTER TABLE ai.audit_log
    ADD COLUMN request_id text,
    ADD COLUMN mode       text   NOT NULL DEFAULT 'help',
    ADD COLUMN tools      text[] NOT NULL DEFAULT '{}';

CREATE INDEX audit_log_request_id ON ai.audit_log (request_id);
