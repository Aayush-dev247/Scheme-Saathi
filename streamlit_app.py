"""Run the original Scheme Saathi React interface as a Streamlit component."""

import logging
import os
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def configure_runtime():
    load_dotenv(ROOT / ".env", override=False)

    try:
        secrets = dict(st.secrets)
    except FileNotFoundError:
        secrets = {}

    for key in (
        "LLM_PROVIDER",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "MIN_SCORE",
    ):
        value = secrets.get(key)

        if isinstance(value, (str, int, float)) and str(value).strip():
            os.environ[key] = str(value).strip()


@st.cache_resource(show_spinner=False)
def get_engine():
    from rag import RAG

    return RAG()


def dispatch(event, completed, engine_factory=get_engine):
    """Validate requests and avoid repeating completed request IDs."""
    if not isinstance(event, dict):
        return None

    request_id = event.get("id")

    if not isinstance(request_id, str) or not re.fullmatch(
        r"[a-zA-Z0-9_-]{8,100}", request_id
    ):
        return None

    if request_id in completed:
        return completed[request_id]

    status = 400
    body = {"error": "Invalid request."}
    action = event.get("action")

    if action == "health":
        try:
            engine = engine_factory()
            engine.load()

            provider = os.getenv("LLM_PROVIDER", "groq")
            key = (
                "GEMINI_API_KEY"
                if provider == "gemini"
                else "GROQ_API_KEY"
            )

            status = 200
            body = {
                "status": "ok",
                "model_ready": True,
                "index_ready": True,
                "chunks": len(engine.rows),
                "provider": provider,
                "llm_configured": bool(os.getenv(key)),
                "error": None,
            }

        except Exception:
            status = 200
            body = {
                "status": "degraded",
                "model_ready": False,
                "index_ready": False,
                "error": (
                    "Knowledge base unavailable. "
                    "Check server configuration."
                ),
            }

    elif action == "ask":
        data = event.get("body")
        question = (
            data.get("question")
            if isinstance(data, dict)
            else None
        )

        if (
            isinstance(question, str)
            and 1 <= len(question.strip()) <= 1500
        ):
            try:
                status = 200
                body = engine_factory().ask(question.strip())

            except Exception:
                logging.getLogger(__name__).exception(
                    "Scholarship retrieval failed"
                )
                status = 503
                body = {
                    "error": (
                        "Scholarship index unavailable. "
                        "Please retry later."
                    )
                }
        else:
            body = {
                "error": "Question must contain 1–1500 characters."
            }

    reply = {
        "id": request_id,
        "status": status,
        "body": body,
    }

    completed[request_id] = reply

    while len(completed) > 32:
        del completed[next(iter(completed))]

    return reply


@st.cache_resource(show_spinner=False)
def get_component():
    return components.declare_component(
        "scheme_saathi_original",
        path=str(ROOT / "streamlit_ui"),
    )


def main():
    st.set_page_config(
        page_title="Scheme Saathi",
        page_icon="🌱",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    try:
        configure_runtime()
    except Exception:
        st.error(
            "Check the app Secrets configuration, "
            "then restart the app."
        )
        st.stop()

    if not (ROOT / "streamlit_ui/index.html").is_file():
        st.error(
            "Original frontend not built. "
            "Run enable_original_ui.py locally "
            "and upload streamlit_ui/."
        )
        st.stop()

    # Fill the browser viewport with the original React component.
    st.markdown(
        """
        <style>
            [data-testid="stHeader"] {
                display: none;
            }

            [data-testid="stMain"] {
                overflow: hidden;
            }

            [data-testid="stMainBlockContainer"] {
                padding: 0 !important;
                max-width: none !important;
            }

            iframe[title*="scheme_saathi_original"] {
                position: fixed !important;
                inset: 0 !important;
                width: 100vw !important;
                height: 100dvh !important;
                border: none !important;
                border-radius: 0 !important;
                display: block !important;
                z-index: 10;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "original_ui_completed" not in st.session_state:
        st.session_state.original_ui_completed = {}
        st.session_state.original_ui_response = None

    event = get_component()(
        response=st.session_state.original_ui_response,
        default=None,
        key="scheme_saathi_original_ui",
    )

    reply = dispatch(
        event,
        st.session_state.original_ui_completed,
    )

    if (
        reply is not None
        and reply != st.session_state.original_ui_response
    ):
        st.session_state.original_ui_response = reply
        st.rerun()


if __name__ == "__main__":
    main()