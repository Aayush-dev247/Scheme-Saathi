FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/app/.cache/huggingface TOKENIZERS_PARALLELISM=false
WORKDIR /app
RUN useradd -m -u 1000 student
COPY requirements.txt ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 && pip install -r requirements.txt
COPY --chown=student:student . .
COPY --from=frontend --chown=student:student /build/dist ./frontend/dist
RUN mkdir -p /app/.cache && chown -R student:student /app
USER student
# Cache embeddings model at build time; an index must be included or built beforehand.
RUN python -c "from embedder import get_model; get_model()"
EXPOSE 7860
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "1", "--threads", "4", "--timeout", "180", "app:app"]
