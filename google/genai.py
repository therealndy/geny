# Compatibility shim so tests and older imports `google.genai` still work.
# It re-exports a minimal Client-compatible facade using google.generativeai.

try:
    from google import generativeai as _ga
except Exception:
    # Allow import failure to raise the same ModuleNotFoundError as before
    raise


class Client:
    """Thin facade exposing `models` and `chats` like older genai.Client.

    This maps to google.generativeai functions/objects where possible.
    Only the bits used by the test-suite are implemented.
    """

    def __init__(self, api_key=None, **kwargs):
        # google.generativeai expects configuration via configure
        if api_key:
            try:
                _ga.configure(api_key=api_key)
            except Exception:
                # fallback to setting an env var as older clients did
                import os

                os.environ.setdefault("GENAI_API_KEY", api_key)
        self._ga = _ga

    class models:
        @staticmethod
        def list():
            return _ga.list_models()

    class chats:
        @staticmethod
        def create(model=None, **kwargs):
            # google.generativeai provides GenerativeModel / ChatSession API.
            # Create a GenerativeModel and start a chat session.
            gm = (
                _ga.GenerativeModel(model)
                if model is not None
                else _ga.get_model(model)
            )
            session = gm.start_chat()

            class ChatWrapper:
                def __init__(self, session):
                    self._session = session

                def send_message(self, message, **kw):
                    # use ChatSession.send_message and map response to have `.text`
                    resp = self._session.send_message(message)

                    def _extract_text(response):
                        try:
                            # Prefer structured candidates -> content -> parts -> text
                            candidates = getattr(response, "candidates", None)
                            if candidates:
                                content = getattr(candidates[0], "content", None)
                                if content is not None:
                                    parts = getattr(content, "parts", None)
                                    if parts:
                                        texts = []
                                        for p in parts:
                                            # part may expose 'text' or nested content
                                            t = getattr(p, "text", None)
                                            if t is None:
                                                # some part objects have 'content' with text
                                                inner = getattr(p, "content", None)
                                                t = (
                                                    getattr(inner, "text", None)
                                                    if inner is not None
                                                    else None
                                                )
                                            if t is None:
                                                # fallback to any string-like attribute
                                                for attr in (
                                                    "text",
                                                    "content",
                                                    "plain_text",
                                                ):
                                                    t = getattr(p, attr, None)
                                                    if t is not None:
                                                        break
                                            if t is None:
                                                t = str(p)
                                            texts.append(t)
                                        return "".join(texts)
                                    # fallback: content may have `.text`
                                    if hasattr(content, "text"):
                                        return content.text
                                    return str(content)

                            # direct properties
                            if hasattr(response, "text"):
                                return response.text
                            if hasattr(response, "content"):
                                return str(response.content)

                            return str(response)
                        except Exception:
                            try:
                                return repr(response)
                            except Exception:
                                return ""

                    class R:
                        def __init__(self, text):
                            self.text = text

                        def __str__(self):
                            return self.text

                    return R(_extract_text(resp))

            return ChatWrapper(session)


# Re-export helpers
def configure(**kwargs):
    return _ga.configure(**kwargs)


__all__ = ["Client", "configure"]
