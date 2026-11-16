"""Streamlit interface for the existing Scheme Saathi RAG engine."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv

from rag import RAG
from scrape import validate_url


ROOT = Path(__file__).resolve().parent

RUNTIME_KEYS = (
    "LLM_PROVIDER",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "MIN_SCORE",
)


def configure_runtime():
    """Load local .env or server-owned Streamlit secrets."""
    load_dotenv(ROOT / ".env", override=False)

    try:
        settings = dict(st.secrets)
    except FileNotFoundError:
        settings = {}
    except Exception:
        raise RuntimeError(
            "Server secrets configuration could not be loaded."
        ) from None

    for name in RUNTIME_KEYS:
        value = settings.get(name)
        if isinstance(value, (str, int, float)) and str(value).strip():
            os.environ[name] = str(value).strip()


@st.cache_resource(show_spinner=False)
def get_engine():
    # Only the public model/index are shared. Chats are session-specific.
    return RAG()


@st.cache_data(show_spinner=False)
def index_summary(manifest_bytes, metadata_bytes):
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    rows = json.loads(metadata_bytes.decode("utf-8"))

    documents = {row["source"]: row for row in rows}
    hosts = sorted({urlparse(row["url"]).hostname for row in rows})

    return {
        "chunks": manifest["chunks"],
        "documents": list(documents.values()),
        "hosts": hosts,
    }


def source_url(source):
    """Allow only official URLs accepted by the existing collector."""
    url = source.get("url", "")

    try:
        validate_url(url)
    except (ValueError, TypeError):
        return None

    url = quote(url, safe=":/?&=%#-._~")

    page = source.get("page")
    if isinstance(page, int) and page > 0:
        url = url.split("#")[0] + f"#page={page}"

    return url


def cited_markdown(answer, sources):
    """Turn numbered citations into official-source links."""

    def replace(match):
        number = int(match.group(1))

        if not 1 <= number <= len(sources):
            return match.group(0)

        url = source_url(sources[number - 1])
        if not url:
            return match.group(0)

        return f"[{number} ↗](<{url}>)"

    return re.sub(r"\[(\d+)\]", replace, answer)


def new_chat():
    chat_id = uuid4().hex

    st.session_state.chats[chat_id] = {
        "title": "New conversation",
        "messages": [],
    }
    st.session_state.active_chat = chat_id

    # Bound session history to five conversations.
    while len(st.session_state.chats) > 5:
        oldest = next(iter(st.session_state.chats))
        del st.session_state.chats[oldest]


def render_assistant(message, position):
    labels = {
        "rag": "AI · cited answer",
        "extractive": "Source excerpts",
        "not_found": "Not found",
        "refused": "Request declined",
    }

    st.caption(labels.get(message["mode"], message["mode"]))
    st.markdown(cited_markdown(message["answer"], message["sources"]))

    for number, source in enumerate(message["sources"], 1):
        title = source.get("title") or source["source"]
        page = (
            f" · PDF page {source['page']}"
            if source.get("page")
            else " · Official webpage"
        )

        with st.expander(f"Source {number} · {title}{page}"):
            st.caption(
                f"Document date: "
                f"{source.get('document_date') or 'not established'}"
                f" · Validity: {source.get('status') or 'unverified'}"
            )

            st.caption(
                f"Applicable from: "
                f"{source.get('applicable_from') or 'not established'}"
                f" · Retrieved: {source.get('last_scraped') or 'unknown'}"
            )

            st.caption(
                f"Cosine similarity: {source['score']:.3f}"
                " — similarity, not eligibility probability"
            )

            st.text(source["text"])

            url = source_url(source)
            if url:
                st.link_button("View official source", url)

    with st.expander("Copy plain answer"):
        st.code(message["answer"], language=None, wrap_lines=True)


def main():
    st.set_page_config(
        page_title="Scheme Saathi · Scholarship Assistant",
        page_icon="🌱",
        layout="wide",
    )

    try:
        configure_runtime()
        summary = index_summary(
            (ROOT / "index/manifest.json").read_bytes(),
            (ROOT / "index/metadata.json").read_bytes(),
        )
    except Exception:
        st.error(
            "The app is not ready. Check index files and "
            "server settings, then restart the app."
        )
        st.stop()

    if "chats" not in st.session_state:
        st.session_state.chats = {}
        new_chat()

    provider = os.getenv("LLM_PROVIDER", "groq")
    key_name = (
        "GEMINI_API_KEY" if provider == "gemini" else "GROQ_API_KEY"
    )
    configured = bool(os.getenv(key_name))

    with st.sidebar:
        st.title("🌱 Scheme Saathi")
        st.caption("OPPORTUNITY, SIMPLIFIED")

        st.button(
            "＋ New conversation",
            on_click=new_chat,
            use_container_width=True,
        )

        chat_ids = list(st.session_state.chats)
        chat_titles = {
            key: value["title"]
            for key, value in st.session_state.chats.items()
        }

        active = st.selectbox(
            "Conversations",
            chat_ids,
            index=chat_ids.index(st.session_state.active_chat),
            format_func=chat_titles.get,
        )
        st.session_state.active_chat = active

        st.divider()
        st.subheader("Official-source knowledge base")

        st.caption(
            f"{len(summary['hosts'])} source websites"
            f" · {summary['chunks']} indexed passages"
        )

        for document in summary["documents"]:
            url = source_url(document)
            if url:
                title = document.get("title") or document["source"]
                st.markdown(f"[{title}](<{url}>)")

        st.divider()

        st.caption(
            "AI provider configured"
            if configured
            else "Excerpt mode · owner API key not configured"
        )

        st.caption(
            "Chats stay in this browser session and may reset on "
            "reload/disconnect. Questions are independent; previous "
            "chat is not supplied as official evidence."
        )

    st.title("A brighter future. A little guidance away.")

    st.write(
        "Scholarship guidance in English, हिंदी and Hinglish "
        "— with evidence you can inspect."
    )

    st.caption(
        "Published guidelines are not confirmation of current deadlines "
        "or your individual eligibility. Verify important details "
        "on official portals."
    )

    if not configured:
        st.info(
            "No owner API key is configured. You can still search "
            "real official passages; responses will be labeled "
            "source excerpts."
        )

    chat = st.session_state.chats[st.session_state.active_chat]

    for position, message in enumerate(chat["messages"]):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["text"])
            else:
                render_assistant(message, position)

    suggested = None

    if not chat["messages"]:
        columns = st.columns(3)

        prompts = [
            "BCA students ke liye scholarship kaunsi hai?",
            "सेंट्रल सेक्टर स्कॉलरशिप का उद्देश्य क्या है?",
            "What is myScheme and how does it work?",
        ]

        for column, prompt in zip(columns, prompts):
            if column.button(prompt, use_container_width=True):
                suggested = prompt

    question = st.chat_input(
        "Ask about a scholarship, eligibility or documents…",
        max_chars=1500,
    )
    question = suggested or question

    if not question:
        return

    question = question.strip()

    if not question or len(question) > 1500:
        st.warning("Please enter a question of 1–1500 characters.")
        return

    if len(chat["messages"]) >= 40:
        st.info(
            "This conversation is full. "
            "Start a new conversation to continue."
        )
        return

    chat["messages"].append({
        "role": "user",
        "text": question,
    })
    chat["title"] = question[:55]

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Reading relevant official documents…"):
            try:
                result = get_engine().ask(question)
            except Exception:
                st.error(
                    "The knowledge base could not be loaded. "
                    "Please try again later or contact the app owner."
                )
                return

        message = {"role": "assistant", **result}
        chat["messages"].append(message)
        render_assistant(message, len(chat["messages"]) - 1)


if __name__ == "__main__":
    main()