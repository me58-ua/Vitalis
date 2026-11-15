"""Optional live smoke check: sends a synthetic answer, never prints secrets."""
from app.ai.onboarding.chat_extraction import extraction_prompt, validate_extraction
from app.ai.onboarding.gemini import AIUnavailable, GeminiOnboardingClient
from app.ai.onboarding.preguntas import PREGUNTAS


def main():
    try:
        response = GeminiOnboardingClient().complete(
            extraction_prompt("height"), PREGUNTAS["height"].text, "Mido 178 centímetros."
        )
        extracted, _ = validate_extraction("height", response)
        if extracted["data"].get("height_cm") != 178:
            print("Gemini smoke check failed: unexpected synthetic extraction.")
            return 1
        print("Gemini smoke check passed: synthetic height extracted correctly.")
        return 0
    except AIUnavailable as error:
        print(str(error))
        return 1
    except ValueError:
        print("Gemini smoke check failed: invalid synthetic extraction.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
