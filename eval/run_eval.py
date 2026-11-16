"""Reproducible local evaluation. Semantic quality of generated prose needs human review."""
import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag import RAG
from scrape import ROOT

def evaluate(engine, questions):
    rows = []
    for q in questions:
        start = time.perf_counter()
        try:
            result = engine.ask(q['question'])
            ids = [int(x) for x in re.findall(r'\[(\d+)\]', result['answer'])]
            sources = result['sources']
            retrieval_hit = any(re.search(q['evidence_regex'], s['text'], re.I) for s in sources) if q['kind'] == 'answerable' else None
            # Mechanical citation integrity is not semantic citation correctness.
            integrity = all(1 <= i <= len(sources) for i in ids) if ids else None
            verbatim = all(sources[i-1]['text'] in result['answer'] for i in ids) if result['mode'] == 'extractive' and ids else None
            rows.append({**q, 'mode': result['mode'], 'retrieval_hit_at_4': retrieval_hit,
                         'citation_integrity': integrity, 'verbatim_support': verbatim,
                         'abstained': result['mode'] in ('not_found','refused'),
                         'latency_s': round(time.perf_counter()-start, 4), 'answer': result['answer'], 'sources': sources})
        except Exception as e:
            rows.append({**q, 'error': type(e).__name__, 'latency_s': round(time.perf_counter()-start,4)})
    def mean(key):
        values=[r[key] for r in rows if r.get(key) is not None]
        return round(statistics.mean(values),4) if values else None
    negative=[r for r in rows if r['kind'] != 'answerable' and 'error' not in r]
    latency=sorted(r['latency_s'] for r in rows if 'error' not in r)
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'questions':len(rows),
            'errors':sum('error' in r for r in rows), 'retrieval_hit_at_4':mean('retrieval_hit_at_4'),
            'citation_id_integrity':mean('citation_integrity'), 'extractive_verbatim_support':mean('verbatim_support'),
            'negative_abstention_rate':round(statistics.mean(r['abstained'] for r in negative),4) if negative else None,
            'mean_latency_s':round(statistics.mean(latency),4) if latency else None,
            'p95_latency_s':latency[min(len(latency)-1,int(len(latency)*.95))] if latency else None,
            'semantic_citation_correctness':None, 'generated_answer_faithfulness':None,
            'notes':['Retrieval score uses hand-authored evidence regexes, not a human semantic judgment.',
                     'Verbatim support measures copied excerpts only; does not establish relevance or completeness.',
                     'Semantic citation correctness and LLM faithfulness require manual review; not measured.',
                     'Latency excludes model warmup. Results are corpus-specific, not a general benchmark.'],
            'results':rows}

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='eval/results.json')
    args=parser.parse_args()
    engine=RAG()
    try: engine.load()
    except Exception:
        print('Evaluation blocked: build the index and download the embedding model first.')
        raise SystemExit(1)
    report=evaluate(engine,json.loads((ROOT/'eval/questions.json').read_text(encoding='utf-8')))
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
