"""Monitoring report from the audit table: no paid tool needed.

    .venv\\Scripts\\python -m app.report            # last 7 days
    .venv\\Scripts\\python -m app.report --days 1

Shows per day: requests by outcome, fallback use, tokens, latency (median and p95),
and how often answers were cut short or blocked. Everything comes from counts and
labels in ai.audit_log; no question text exists there to show.
"""

import argparse
import asyncio

import asyncpg

from .config import get_settings

SUMMARY = """
SELECT (created_at AT TIME ZONE 'Asia/Kolkata')::date AS day,
       mode,
       count(*)                                                     AS requests,
       count(*) FILTER (WHERE outcome = 'answered')                 AS answered,
       count(*) FILTER (WHERE outcome IN ('refused_advice', 'refused_scope', 'not_my_data')) AS refused,
       count(*) FILTER (WHERE outcome = 'insufficient_context')     AS not_covered,
       count(*) FILTER (WHERE outcome IN ('ungrounded_blocked', 'figures_only')) AS blocked_or_figures,
       count(*) FILTER (WHERE outcome = 'llm_unavailable')          AS unavailable,
       count(*) FILTER (WHERE outcome = 'error')                    AS errors,
       count(*) FILTER (WHERE provider = 'gemini')                  AS gemini_fallback,
       count(*) FILTER (WHERE finish_reason = 'length')             AS cut_short,
       coalesce(sum(input_tokens + output_tokens), 0)               AS tokens,
       percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms)::int AS p50_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::int AS p95_ms
FROM ai.audit_log
WHERE created_at > now() - make_interval(days => $1)
GROUP BY 1, 2
ORDER BY 1 DESC, 2
"""

TOOLS = """
SELECT tool, count(*) AS calls
FROM ai.audit_log, unnest(tools) AS tool
WHERE created_at > now() - make_interval(days => $1)
GROUP BY tool ORDER BY calls DESC
"""


async def report(days: int) -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("AI_DATABASE_URL is not set")
    conn = await asyncpg.connect(settings.database_url.get_secret_value(), timeout=5)
    try:
        rows = await conn.fetch(SUMMARY, days)
        tools = await conn.fetch(TOOLS, days)
    finally:
        await conn.close()
    if not rows:
        print(f"No assistant requests in the last {days} day(s).")
        return
    columns = list(rows[0].keys())
    widths = [max(len(c), *(len(str(r[c])) for r in rows)) for c in columns]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    for r in rows:
        print("  ".join(str(r[c]).ljust(w) for c, w in zip(columns, widths)))
    if tools:
        print("\nTool calls: " + ", ".join(f"{t['tool']}={t['calls']}" for t in tools))


def main() -> None:
    parser = argparse.ArgumentParser(description="Assistant usage and health from the audit log")
    parser.add_argument("--days", type=int, default=7)
    asyncio.run(report(max(1, parser.parse_args().days)))


if __name__ == "__main__":
    main()
