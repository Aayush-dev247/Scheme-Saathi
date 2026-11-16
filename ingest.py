"""Page-aware ingestion. No chunks cross a PDF page boundary."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from pypdf import PdfReader
from scrape import ROOT, validate_url

def chunk_text(text, size=180, overlap=40):
    if not 0 <= overlap < size:
        raise ValueError('Require 0 <= overlap < size')
    words = text.split()
    for start in range(0, len(words), size - overlap):
        yield ' '.join(words[start:start + size])
        if start + size >= len(words):
            break

def documents():
    for path in sorted((ROOT / 'data/pdfs').glob('*.pdf')):
        sidecar = path.with_suffix('.pdf.json')
        if not sidecar.exists():
            raise ValueError(f'Missing official-source metadata: {path.name}')
        meta = json.loads(sidecar.read_text(encoding='utf-8'))
        validate_url(meta['url'])
        if meta.get('superseded_by'):
            print(f"Skipping superseded source: {path.name}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta['sha256']:
            raise ValueError(f'PDF checksum mismatch: {path.name}')
        for page, item in enumerate(PdfReader(path).pages, start=1):
            if meta.get('include_pages') and page not in meta['include_pages']:
                continue
            text = item.extract_text() or ''
            if not text.strip():
                print(f'Warning: no extractable text: {path.name}, page {page}')
            yield meta, page, text
    for path in sorted((ROOT / 'data/scraped').glob('*.json')):
        meta = json.loads(path.read_text(encoding='utf-8'))
        validate_url(meta['url'])
        yield meta, None, meta['text']

def main():
    import faiss
    from embedder import embed, MODEL_NAME
    rows = []
    for meta, page, text in documents():
        for passage in chunk_text(text):
            rows.append({k: meta.get(k) for k in ['source','url','title','status','document_date','last_scraped','applicable_from']} | {'page': page, 'text': passage})
    if not rows:
        raise SystemExit('No documents. Run scrape.py --manifest data/sources.json first.')
    vectors = embed([r['text'] for r in rows])
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    folder = ROOT / 'index'
    folder.mkdir(exist_ok=True)
    faiss.write_index(index, str(folder / 'vectors.faiss.tmp'))
    os.replace(folder / 'vectors.faiss.tmp', folder / 'vectors.faiss')
    (folder / 'metadata.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    (folder / 'manifest.json').write_text(json.dumps({'model': MODEL_NAME, 'chunks': len(rows), 'dimension': vectors.shape[1], 'created_at': datetime.now(timezone.utc).isoformat()}, indent=2), encoding='utf-8')
    print(f'Indexed {len(rows)} page-aware chunks')

if __name__ == '__main__':
    main()
