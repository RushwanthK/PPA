-- 0002: per-user daily usage (quotas) and an audit log of assistant requests.

-- One row per user per day. Requests are reserved atomically before any work,
-- so concurrent requests cannot both slip under the limit.
CREATE TABLE ai.usage_daily (
    user_id       bigint  NOT NULL,
    day           date    NOT NULL,   -- India Standard Time day
    requests      integer NOT NULL DEFAULT 0,
    input_tokens  integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- What happened for each request. Privacy: the question text is NOT stored,
-- only its hash and length, so the log can show patterns without keeping
-- personal content.
CREATE TABLE ai.audit_log (
    id               bigserial   PRIMARY KEY,
    created_at       timestamptz NOT NULL DEFAULT now(),
    user_id          bigint      NOT NULL,
    outcome          text        NOT NULL,
    question_sha256  text        NOT NULL,
    question_chars   integer     NOT NULL,
    sources          text[]      NOT NULL DEFAULT '{}',
    top_similarity   real,
    provider         text,
    model            text,
    prompt_version   text,
    input_tokens     integer     NOT NULL DEFAULT 0,
    output_tokens    integer     NOT NULL DEFAULT 0,
    latency_ms       integer     NOT NULL
);

CREATE INDEX audit_log_user_created ON ai.audit_log (user_id, created_at DESC);
