import json
import re

import httpx

from app.config import get_settings

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


class LLMError(Exception):
    """Échec côté LLM (clé absente, erreur réseau/API, réponse inexploitable)."""


def chat_json(system: str, user: str, *, max_tokens: int, temperature: float = 0.3) -> dict:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise LLMError("OPENROUTER_API_KEY n'est pas renseignée dans backend/.env")
    payload: dict = {
        "model": settings.openrouter_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Sans raisonnement : 5 à 10 fois plus rapide, et le modèle respecte mieux la langue demandée
        "reasoning": {"enabled": False},
    }
    try:
        response = httpx.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "X-Title": settings.app_name,
            },
            json=payload,
            timeout=90,
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"OpenRouter injoignable : {type(exc).__name__}") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise LLMError(f"Réponse OpenRouter illisible (HTTP {response.status_code})") from exc
    if response.status_code != 200 or "error" in body:
        message = (body.get("error") or {}).get("message") or f"HTTP {response.status_code}"
        raise LLMError(f"OpenRouter : {message}")
    try:
        choice = body["choices"][0]
        content = choice["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Réponse OpenRouter sans contenu") from exc
    if choice.get("finish_reason") == "length":
        raise LLMError("Réponse du modèle tronquée (max_tokens atteint)")
    try:
        data = json.loads(_FENCE.sub("", content.strip()))
    except ValueError as exc:
        raise LLMError("Le modèle n'a pas renvoyé un JSON valide") from exc
    if not isinstance(data, dict):
        raise LLMError("Le modèle n'a pas renvoyé un objet JSON")
    return data
