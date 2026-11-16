# Implementation notes

## Official-source ingestion
Added `scrape.py`, `ingest.py`, and `embedder.py` with HTTPS host allowlisting, robots checks, bounded downloads, provenance timestamps, and SHA-256 metadata. PDF extraction uses physical, one-based page numbers; 180-word chunks overlap by 40 words and never cross pages.

## Retrieval and generation
Added normalized multilingual embeddings, a 384-dimensional FAISS inner-product index, and top-four retrieval with a configurable threshold. Groq and Gemini adapters request structured cited claims; invalid citation IDs or API errors fall back to explicitly labeled verbatim excerpts. This does not prove semantic support of generated claims.

## Backend and interface
Added validated Flask endpoints and a same-origin React/Vite/Tailwind interface with landing screen, local conversation history, dark mode, suggestions, source dialogs, copy controls, and request errors. No API credentials reach the frontend; missing index/model state is reported as degraded.

## Validation and deployment
Added 36 multilingual evaluation cases, backend tests including real page provenance, production asset compilation, and a non-root multi-stage Docker image for port 7860. The checked-in results distinguish mechanical checks from unmeasured semantic quality; Docker and external LLM calls were not executed.

## Data availability and evaluation correction
Two Ministry PDF links returned 404; AICTE and Rajasthan robots endpoints returned 503. An official Meghalaya mirror supplied a seven-page July 2019 PDF; myScheme supplied one readable page. Historical data is never labeled current. Following the baseline evaluation, conservative off-topic, private-record, and future-year guards were added; the final evaluation reuses the same cases and is not a held-out benchmark.


## 16 November 2026 — reviewed BCA data update
Added a four-page official NSP CSSS PDF and the five-page Sarswati annexure of a 14-page official Kerala-hosted AICTE circular. Raw PDFs remain unchanged; the 2019 CSSS sidecar is marked superseded and excluded from the default index.

Added course abbreviation expansion and a small course-match ranking bonus. For course discovery, a same-page eligibility passage can occupy one of the four evidence slots, preserving qualifications even when a matching chunk begins after them; raw cosine scores remain unchanged and contextual scores can fall below the seed threshold.

Made text reads explicitly UTF-8 for Windows and changed the default Groq model to the ID verified in the user's account. Prompt guidance preserves girls-only, income and admission restrictions and distinguishes course-specific evidence from general-degree scope; no individual eligibility or 2026-27 deadline is inferred.

The update installer backs up only files it changes, excludes .env and frontend files, and installs the rebuilt index without another model download. Thirty-eight tests passed; live generation on the new corpus was not tested in this workspace because no key was available.
