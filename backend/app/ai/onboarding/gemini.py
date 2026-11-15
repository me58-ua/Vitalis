"""Stateless Gemini extraction. Never log answers, credentials or provider errors."""
import json

from google import genai
from google.genai import types

from app.config import settings


class AIUnavailable(Exception):
    pass


class GeminiOnboardingClient:
    def complete(self, instructions: str, question: str, answer: str) -> dict:
        key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY or settings.AI_API_KEY
        if not key:
            raise AIUnavailable("La IA no está configurada. Inténtalo más tarde.")
        try:
            with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000)) as client:
                contents = json.dumps({"question": question, "answer": answer}, ensure_ascii=False)
                try:
                    interaction = client.interactions.create(
                        model=settings.GEMINI_MODEL,
                        system_instruction=instructions,
                        input=contents,
                        store=False,
                        timeout=30,
                    )
                    text = interaction.output_text or ""
                except Exception as error:
                    # Some accounts expose models through generateContent before
                    # the Interactions endpoint. Use the same model and instructions.
                    if (getattr(error, "status_code", None) or getattr(error, "code", None)) != 404:
                        raise
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL, contents=contents,
                        config=types.GenerateContentConfig(system_instruction=instructions,
                            response_mime_type="application/json", temperature=0),
                    )
                    text = response.text or ""
            # Accept a JSON code fence, but never execute or display model markup.
            if text.strip().startswith("```"):
                text = "\n".join(text.strip().splitlines()[1:-1])
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError("Expected an object")
            return payload
        except Exception as error:
            # Provider exceptions can include request bodies. Do not propagate them.
            code = getattr(error, "status_code", None) or getattr(error, "code", None)
            if code in {400, 401, 403, 404, 429}:
                messages = {
                    400: "Gemini ha rechazado la solicitud. Revisa la configuración del modelo y la clave en el servidor.",
                    401: "Gemini no ha aceptado la clave del servidor. Revisa su configuración.",
                    403: "El servidor no tiene permiso para usar Gemini. Revisa la clave y sus permisos.",
                    404: "El modelo de Gemini configurado no está disponible para esta clave. Revisa GEMINI_MODEL.",
                    429: "Gemini ha alcanzado su límite de uso. Espera un momento e inténtalo de nuevo.",
                }
                # Classify common account restrictions without returning provider
                # messages, which may contain the API key or project identifiers.
                provider_message = str(error).casefold()
                if code == 403 and "leaked" in provider_message:
                    raise AIUnavailable("Google ha bloqueado la clave de Gemini por una posible filtración. Sustitúyela en el servidor.") from None
                if code == 403 and ("referer" in provider_message or "referrer" in provider_message):
                    raise AIUnavailable("La clave de Gemini tiene restricciones de navegador y no permite llamadas desde el servidor. Revisa sus restricciones.") from None
                if code == 403 and ("has not been used" in provider_message or "disabled" in provider_message):
                    raise AIUnavailable("La API de Gemini no está habilitada para esta clave. Revisa el proyecto de Google.") from None
                raise AIUnavailable(messages[code]) from None
            raise AIUnavailable("No se pudo interpretar tu respuesta con la IA. Inténtalo de nuevo; seguimos en la misma pregunta.") from None
