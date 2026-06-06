"""Generación de texto con Google Gemini (único proveedor).

Se DESACTIVA el modo "thinking" (thinking_budget=0): respuestas directas, más
completas dentro del presupuesto de salida y MUCHO más baratas. Tras cada llamada
se guarda el uso real de tokens en LAST_USAGE para poder reportar el costo.
"""

from __future__ import annotations

from .env import GEMINI_API_KEY, GEMINI_CHAT_MODEL

# Uso de tokens de la última llamada Gemini (para reportar el costo real).
LAST_USAGE: dict = {}

# Tarifas aproximadas en USD por 1M de tokens (entrada, salida).
_RATES = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.1-flash-lite": (0.10, 0.40),  # estimado (tier lite; precio no confirmado)
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.0),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rin, rout = _RATES.get(model, (0.30, 2.50))
    return input_tokens / 1e6 * rin + output_tokens / 1e6 * rout


def health(timeout: int = 3) -> bool:
    """True si Gemini está configurado (hay API key)."""
    return bool(GEMINI_API_KEY)


def _chat_gemini(messages: list[dict], model: str | None = None, temperature: float = 0.2, max_tokens: int = 1536) -> str:
    from google import genai as gemini_client
    from google.genai import types

    if not GEMINI_API_KEY:
        raise RuntimeError("Falta GEMINI_API_KEY: define tu API key de Gemini en .env")

    client = gemini_client.Client(api_key=GEMINI_API_KEY)
    model = model or GEMINI_CHAT_MODEL

    system = ""
    contents: list = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            role = "user" if m["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))

    def _cfg(thinking_off: bool):
        kw = dict(system_instruction=system or None, temperature=temperature, max_output_tokens=max_tokens)
        if thinking_off:
            kw["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kw)

    try:
        resp = client.models.generate_content(model=model, contents=contents, config=_cfg(True))
    except Exception as e:  # noqa: BLE001
        # Algunos modelos no aceptan thinking_config -> reintenta sin desactivarlo.
        if "thinking" in str(e).lower() or "thinking_config" in str(e).lower():
            resp = client.models.generate_content(model=model, contents=contents, config=_cfg(False))
        else:
            raise

    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        LAST_USAGE.clear()
        LAST_USAGE.update(
            model=model,
            input=getattr(u, "prompt_token_count", 0) or 0,
            output=getattr(u, "candidates_token_count", 0) or 0,
            thoughts=getattr(u, "thoughts_token_count", 0) or 0,
        )
    return (resp.text or "").strip()


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.2, **kwargs) -> str:
    """Completa un chat con Gemini."""
    return _chat_gemini(messages, model=model, temperature=temperature)
