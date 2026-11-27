"""Builds the AssistantService from settings. Returns None (and logs why) when a
dependency is missing, so the service still starts and /v1/ask answers 503."""

import logging

import httpx

from ..config import Settings
from ..db import Database
from ..llm.base import ChatModel
from ..llm.gemini import GeminiChatModel, GeminiToolChatModel
from ..llm.groq import GroqChatModel
from ..llm.router import FallbackChatModel
from ..rag.embeddings import GeminiEmbedder
from .data_agent import DataAgent
from .flask_data import FlaskDataClient
from .service import AssistantService

log = logging.getLogger("ppa_ai.assistant")


def _secret(value) -> str:
    return value.get_secret_value().strip() if value is not None else ""


def build_chat_model(settings: Settings, http: httpx.AsyncClient) -> ChatModel | None:
    models: list[ChatModel] = []
    if _secret(settings.groq_api_key):
        models.append(GroqChatModel(_secret(settings.groq_api_key), settings.groq_model, http,
                                    timeout=settings.llm_timeout_seconds))
    if _secret(settings.gemini_api_key):
        models.append(GeminiChatModel(_secret(settings.gemini_api_key), settings.gemini_model, http,
                                      timeout=settings.llm_timeout_seconds))
    return FallbackChatModel(models) if models else None


async def build_assistant(settings: Settings, db: Database, http: httpx.AsyncClient) -> AssistantService | None:
    if not _secret(settings.gemini_api_key):
        log.warning("Assistant disabled: GEMINI_API_KEY is needed for query embeddings")
        return None
    chat = build_chat_model(settings, http)
    if chat is None:
        log.warning("Assistant disabled: no chat model key configured")
        return None
    if not await db.connect():
        log.warning("Assistant not ready: database unavailable")
        return None
    embedder = GeminiEmbedder(_secret(settings.gemini_api_key), settings.gemini_embedding_model,
                              settings.embedding_dimensions, client=http,
                              texts_per_minute=settings.gemini_embed_texts_per_minute, max_retries=1)
    # My-data mode: Groq first; Gemini takes any trip Groq fails (owner's decision, Nov 27:
    # their PPA data may go to Gemini; keys and tokens never do). Until Nov 26 it was Groq only.
    data_agent = None
    if _secret(settings.groq_api_key):
        groq = GroqChatModel(_secret(settings.groq_api_key), settings.groq_model, http,
                             timeout=settings.llm_timeout_seconds)
        gemini = GeminiToolChatModel(_secret(settings.gemini_api_key), settings.gemini_model, http,
                                     timeout=settings.llm_timeout_seconds)
        data_agent = DataAgent(groq, FlaskDataClient(settings.flask_api_url, http,
                                                     timeout=settings.flask_data_timeout_seconds),
                               max_tokens=settings.answer_max_tokens, fallback=gemini)
    else:
        log.warning("My-data mode disabled: it needs GROQ_API_KEY")
    return AssistantService(db.pool, embedder, chat, settings, data_agent=data_agent)
