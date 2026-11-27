"""Try providers in order; fall back only when the failure is about availability.

Free tiers rate-limit often. Instead of making the user wait for a quota window to
reset, the next provider answers. A non-retryable error (for example HTTP 400) means
the request itself is wrong, so it surfaces immediately instead of being hidden.
"""

import logging

from .base import ChatModel, LLMError, LLMResult, Message

log = logging.getLogger("ppa_ai.llm")


class FallbackChatModel:
    def __init__(self, models: list[ChatModel]):
        if not models:
            raise ValueError("at least one model is required")
        self.models = models
        self.provider = "+".join(m.provider for m in models)
        self.model = models[0].model

    async def complete(self, messages: list[Message], *, max_tokens: int, temperature: float = 0.2) -> LLMResult:
        errors: list[LLMError] = []
        for model in self.models:
            try:
                return await model.complete(messages, max_tokens=max_tokens, temperature=temperature)
            except LLMError as exc:
                if not exc.retryable:
                    raise
                log.warning("%s unavailable (%s); trying next provider", exc.provider, exc)
                errors.append(exc)
        if len(errors) == 1:
            raise errors[0]
        # Every provider is down or rate-limited. The user can retry as soon as the
        # first one recovers, so report the shortest known wait.
        waits = [e.retry_after for e in errors]
        raise LLMError("All providers failed: " + "; ".join(str(e) for e in errors), provider=self.provider,
                       retryable=True, retry_after=min(waits) if all(w is not None for w in waits) else None,
                       daily=all(e.daily for e in errors))
