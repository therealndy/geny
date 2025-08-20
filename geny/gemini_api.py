"""GenAI wrapper for local dev and production.

Behavior:
- Attempt to read API key from environment variable `GENAI_API_KEY` or from
  Google Cloud Secret Manager (secret name configurable). If no key is
  available, fall back to a safe local echo implementation for tests.
- Exposes an async `generate_reply(prompt)` function used by the app.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None
    # Allows offline tests to run without Google Gemini installed
from google.cloud import secretmanager

logger = logging.getLogger(__name__)

# Configuration: model and secret names are configurable via environment.
MODEL = os.getenv("GENAI_MODEL", "models/gemini-2.5-flash")
SECRET_PROJECT = os.getenv("GENAI_SECRET_PROJECT", "geny-469516")
SECRET_NAME = os.getenv("GENAI_SECRET_NAME", "genai-api-key")


def _get_api_key_from_secret_manager(project: str = SECRET_PROJECT, secret_name: str = SECRET_NAME) -> Optional[str]:
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("utf-8")
        return payload
    except Exception as e:
        logger.debug("Could not fetch secret from Secret Manager: %s", e)
        return None


# Resolve API key: env var takes precedence, then Secret Manager.
API_KEY = os.getenv("GENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    API_KEY = _get_api_key_from_secret_manager()


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF = "half_open"

    def __init__(self, fail_threshold: int = 5, recovery_timeout: int = 60):
        self.fail_threshold = fail_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitBreaker.CLOSED
        self._fail_count = 0
        self._opened_at = 0

    def record_success(self):
        self._fail_count = 0
        self._state = CircuitBreaker.CLOSED

    def record_failure(self):
        self._fail_count += 1
        if self._fail_count >= self.fail_threshold:
            self._state = CircuitBreaker.OPEN
            self._opened_at = time.time()

    def allow_request(self) -> bool:
        if self._state == CircuitBreaker.OPEN:
            if time.time() - self._opened_at > self.recovery_timeout:
                self._state = CircuitBreaker.HALF
                return True
            return False
        return True


_circuit = CircuitBreaker(fail_threshold=3, recovery_timeout=30)


def _jittered_backoff(attempt: int, base: float = 0.5, cap: float = 10.0) -> float:
    expo = min(cap, base * (2 ** attempt))
    return expo * (0.5 + random.random() * 0.5)


async def _call_gemini(prompt: str, max_retries: int = 3, timeout: int = 15) -> str:
    if not API_KEY:
        msg = "[Gemini error] Missing API key. Set GENAI_API_KEY or configure Secret Manager."
        logger.error(msg)
        return msg

    if not _circuit.allow_request():
        logger.warning("Circuit breaker open; failing fast")
        return "[Gemini error] Circuit open - upstream unavailable"

    system_prompt = "Du är Geny, en AI-assistent med empati och intelligens. Svara kort och hjälpsamt."

    last_err = None
    for attempt in range(max_retries):
        def blocking_call():
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel(MODEL)
            response = model.generate_content(f"{system_prompt}\n{prompt}")
            # Gemini returns a response object with .text or .candidates[0].text
            if hasattr(response, "text"):
                return response.text
            elif hasattr(response, "candidates") and response.candidates:
                return response.candidates[0].text
            return str(response)

        try:
            text = await asyncio.wait_for(asyncio.to_thread(blocking_call), timeout=timeout)
            logger.info("Gemini reply received (len=%d)", len(text))
            _circuit.record_success()
            return text
        except asyncio.TimeoutError as e:
            last_err = e
            logger.exception("Gemini API timeout on attempt %d: %s", attempt + 1, str(e))
            _circuit.record_failure()
        except Exception as e:
            last_err = e
            err_text = str(e)
            logger.exception("Gemini API error on attempt %d: %s", attempt + 1, err_text)
            if "401" in err_text or "API key not valid" in err_text or "Unauthorized" in err_text:
                _circuit.record_failure()
                return f"[Gemini 401] {err_text}"
            _circuit.record_failure()

        backoff = _jittered_backoff(attempt)
        await asyncio.sleep(backoff)

    return f"[Gemini error] Failed after {max_retries} attempts: {last_err}"


async def generate_reply(prompt: str, *, max_retries: int = 3, timeout: Optional[float] = 15) -> str:
    """Public async function used by the app.

    If an API key is configured (env or Secret Manager) this will call Gemini.
    Otherwise it falls back to a safe local echo reply for offline/dev.
    """
    # If we have an API key, call the real Gemini client
    if API_KEY:
        return await _call_gemini(prompt, max_retries=max_retries, timeout=timeout)

    await asyncio.sleep(0)
    # Extract user message
    try:
        parts = [p.strip() for p in prompt.splitlines() if p.strip()]
        user_msg = parts[-1] if parts else prompt
    except Exception:
        user_msg = prompt

    # Friendly, personal fallback
    reply = f"I think... {user_msg} I'm not connected to Gemini right now, but I'm here to listen and help! What would you like to talk about?"
    return reply
