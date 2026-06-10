"""Provider abstraction: returns an OpenAI-compatible client + resolves the API key.

All three supported providers expose an OpenAI-compatible /chat/completions
endpoint, so we use the openai SDK with a swapped base_url + key.
"""
from openai import OpenAI

from app.config import get_settings

# Base URLs for OpenAI-compatible endpoints.
_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": None,  # SDK default
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def get_client() -> OpenAI:
    """Build an OpenAI-compatible client for the configured provider."""
    settings = get_settings()
    provider = settings.extraction_provider.lower()

    key_map = {
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
    }
    if provider not in _BASE_URLS:
        raise ValueError(f"Unknown EXTRACTION_PROVIDER: {provider}")

    api_key = key_map[provider]
    if not api_key:
        raise ValueError(f"No API key set for provider '{provider}'. Check your .env.")

    base_url = _BASE_URLS[provider]
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)