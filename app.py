"""Same-origin Flask API and built React assets."""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
load_dotenv()
from rag import RAG

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 8192
engine = RAG()

@app.get('/api/health')
def health():
    try:
        engine.load()
        ready = True
    except Exception:
        ready = False
    provider = os.getenv('LLM_PROVIDER', 'groq')
    key = os.getenv('GEMINI_API_KEY' if provider == 'gemini' else 'GROQ_API_KEY')
    return jsonify(status='ok' if ready else 'degraded', model_ready=ready,
                   index_ready=engine.index is not None, chunks=len(engine.rows),
                   llm_configured=bool(key), provider=provider, error=engine.error)

@app.post('/api/ask')
def ask():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('question'), str):
        return jsonify(error='Provide a JSON object with a question string.'), 400
    question = data['question'].strip()
    if not question or len(question) > 1500:
        return jsonify(error='Question must contain 1–1500 characters.'), 400
    try:
        return jsonify(engine.ask(question))
    except Exception:
        app.logger.exception('Retrieval failed')
        return jsonify(error='Scholarship index unavailable. Run ingestion and retry.'), 503

@app.get('/')
@app.get('/<path:path>')
def frontend(path=''):
    if path.startswith('api/'):
        return jsonify(error='Unknown endpoint'), 404
    dist = ROOT / 'frontend/dist'
    if not (dist / 'index.html').exists():
        return jsonify(error='Frontend not built. Run npm ci && npm run build in frontend/.'), 503
    if path and (dist / path).is_file():
        return send_from_directory(dist, path)
    return send_from_directory(dist, 'index.html')

@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify(error=error.description), error.code

@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return response

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '7860')))
    parser.add_argument('--strictPort', action='store_true')
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)
