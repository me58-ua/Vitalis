"""Synthetic provider diagnostic. Output only status and allowlisted reason codes."""
import json
import re

from google import genai
from google.genai import types
from app.config import settings


def safe_error(error):
    code = getattr(error, 'status_code', None) or getattr(error, 'code', None)
    reasons = set()
    payloads = [getattr(error, 'details', None), getattr(error, 'body', None)]
    def visit(value):
        if isinstance(value, str):
            try:
                visit(json.loads(value))
            except (ValueError, TypeError):
                pass
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {'reason', 'status'} and isinstance(item, str) and re.fullmatch(r'[A-Z][A-Z_]{2,80}', item):
                    reasons.add(item)
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for payload in payloads:
        visit(payload)
    # Emit categories, never the message itself or project identifiers.
    message = str(error).lower()
    for marker, label in [('project has been denied', 'PROJECT_ACCESS_DENIED'), ('unrestricted', 'UNRESTRICTED_KEY'),
                          ('leaked', 'LEAKED_KEY'), ('referrer', 'REFERRER_RESTRICTION'), ('referer', 'REFERRER_RESTRICTION'),
                          ('service account', 'SERVICE_ACCOUNT_PERMISSION'), ('disabled', 'API_DISABLED'),
                          ('ip address', 'IP_RESTRICTION'), ('location', 'LOCATION_RESTRICTION')]:
        if marker in message:
            reasons.add(label)
    provider_message = getattr(error, 'message', None)
    if not isinstance(provider_message, str):
        provider_message = ''
    # Only the message field, never a request/response dump. Redact configured
    # keys as well as URLs and opaque identifiers before emitting diagnostics.
    for secret in (settings.GEMINI_API_KEY, settings.GOOGLE_API_KEY, settings.AI_API_KEY):
        if secret:
            provider_message = provider_message.replace(secret, '[REDACTED]')
    provider_message = re.sub(r'https?://\S+', '[URL]', provider_message)
    provider_message = re.sub(r'\b[A-Za-z0-9_-]{24,}\b', '[REDACTED]', provider_message)
    return {'http_status': code if isinstance(code, int) else None, 'reasons': sorted(reasons), 'message': provider_message[:600]}


def main():
    key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY or settings.AI_API_KEY
    if not key:
        print('No Gemini key configured.')
        return 1
    with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=15000)) as client:
        for name, call in [
            ('interactions', lambda: client.interactions.create(model=settings.GEMINI_MODEL, input='Reply with the word OK.', store=False, timeout=15)),
            ('generate_content', lambda: client.models.generate_content(model=settings.GEMINI_MODEL, contents='Reply with the word OK.')),
        ]:
            try:
                call()
                print(json.dumps({'endpoint': name, 'success': True}))
            except Exception as error:
                print(json.dumps({'endpoint': name, **safe_error(error)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
