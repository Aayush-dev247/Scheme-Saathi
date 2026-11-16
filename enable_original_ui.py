"""Build your existing React frontend for Streamlit without redesigning it.
Run: python -X utf8 enable_original_ui.py (beside app.py).
Node/npm are required locally; Streamlit Cloud receives the compiled assets.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


APP = '"""Run the original Scheme Saathi React interface as a Streamlit component."""\nimport json\nimport logging\nimport os\nimport re\nfrom pathlib import Path\n\nimport streamlit as st\nimport streamlit.components.v1 as components\nfrom dotenv import load_dotenv\n\nROOT = Path(__file__).resolve().parent\n\n\ndef configure_runtime():\n    load_dotenv(ROOT / \'.env\', override=False)\n    try:\n        secrets = dict(st.secrets)\n    except FileNotFoundError:\n        secrets = {}\n    for key in (\'LLM_PROVIDER\', \'GROQ_API_KEY\', \'GROQ_MODEL\',\n                \'GEMINI_API_KEY\', \'GEMINI_MODEL\', \'MIN_SCORE\'):\n        value = secrets.get(key)\n        if isinstance(value, (str, int, float)) and str(value).strip():\n            os.environ[key] = str(value).strip()\n\n\n@st.cache_resource(show_spinner=False)\ndef get_engine():\n    from rag import RAG\n    return RAG()\n\n\ndef dispatch(event, completed, engine_factory=get_engine):\n    """Validate one component request; never rerun a completed request ID."""\n    if not isinstance(event, dict):\n        return None\n    request_id = event.get(\'id\')\n    if not isinstance(request_id, str) or not re.fullmatch(r\'[a-zA-Z0-9_-]{8,100}\', request_id):\n        return None\n    if request_id in completed:\n        return completed[request_id]\n    status, body = 400, {\'error\': \'Invalid request.\'}\n    action = event.get(\'action\')\n    if action == \'health\':\n        try:\n            engine = engine_factory()\n            engine.load()\n            provider = os.getenv(\'LLM_PROVIDER\', \'groq\')\n            key = \'GEMINI_API_KEY\' if provider == \'gemini\' else \'GROQ_API_KEY\'\n            status, body = 200, {\n                \'status\': \'ok\', \'model_ready\': True, \'index_ready\': True,\n                \'chunks\': len(engine.rows), \'provider\': provider,\n                \'llm_configured\': bool(os.getenv(key)), \'error\': None,\n            }\n        except Exception:\n            status, body = 200, {\n                \'status\': \'degraded\', \'model_ready\': False, \'index_ready\': False,\n                \'error\': \'Knowledge base unavailable. Check server configuration.\',\n            }\n    elif action == \'ask\':\n        data = event.get(\'body\')\n        question = data.get(\'question\') if isinstance(data, dict) else None\n        if isinstance(question, str) and 1 <= len(question.strip()) <= 1500:\n            try:\n                status, body = 200, engine_factory().ask(question.strip())\n            except Exception:\n                logging.getLogger(__name__).exception(\'Scholarship retrieval failed\')\n                status, body = 503, {\'error\': \'Scholarship index unavailable. Please retry later.\'}\n        else:\n            body = {\'error\': \'Question must contain 1–1500 characters.\'}\n    reply = {\'id\': request_id, \'status\': status, \'body\': body}\n    completed[request_id] = reply\n    while len(completed) > 32:\n        del completed[next(iter(completed))]\n    return reply\n\n\n@st.cache_resource(show_spinner=False)\ndef get_component():\n    return components.declare_component(\'scheme_saathi_original\', path=str(ROOT / \'streamlit_ui\'))\n\n\ndef main():\n    st.set_page_config(page_title=\'Scheme Saathi\', page_icon=\'🌱\', layout=\'wide\', initial_sidebar_state=\'collapsed\')\n    try:\n        configure_runtime()\n    except Exception:\n        st.error(\'Check the app Secrets configuration, then restart the app.\')\n        st.stop()\n    if not (ROOT / \'streamlit_ui/index.html\').is_file():\n        st.error(\'Original frontend not built. Run enable_original_ui.py locally and upload streamlit_ui/.\')\n        st.stop()\n    # Styling only the Streamlit shell; React\'s original styles remain unchanged.\n    st.markdown(\'\'\'<style>\n        [data-testid="stHeader"] {display:none;}\n        [data-testid="stMainBlockContainer"] {padding:0!important;max-width:none!important;}\n        [data-testid="stMain"] {overflow-x:hidden;}\n        [data-testid="stElementContainer"]:has(iframe) {margin:0;}\n        iframe[title*="scheme_saathi_original"] {display:block;border:0;}\n        </style>\'\'\', unsafe_allow_html=True)\n    if \'original_ui_completed\' not in st.session_state:\n        st.session_state.original_ui_completed = {}\n        st.session_state.original_ui_response = None\n    event = get_component()(response=st.session_state.original_ui_response,\n                            default=None, key=\'scheme_saathi_original_ui\')\n    # A stable component key keeps the React app mounted across Python reruns.\n    reply = dispatch(event, st.session_state.original_ui_completed)\n    if reply is not None and reply != st.session_state.original_ui_response:\n        st.session_state.original_ui_response = reply\n        st.rerun()\n\n\nif __name__ == \'__main__\':\n    main()\n'

BRIDGE = "// Preserve React's fetch-based UI; route only its two API calls to Python.\nimport { Streamlit } from 'streamlit-component-lib';\n\nconst originalFetch = window.fetch.bind(window);\nconst queue = [];\nlet active = null;\nlet ready = false;\n\nfunction pump() {\n  if (!ready || active) return;\n  while (queue.length && queue[0].cancelled) queue.shift();\n  active = queue.shift() || null;\n  if (active) Streamlit.setComponentValue(active.event);\n}\n\nfunction resize() {\n  // An iframe cannot read a cross-origin parent's viewport. Use available screen\n  // height as a bounded initial size; React retains its own responsive layout.\n  const available = window.screen?.availHeight || 900;\n  Streamlit.setFrameHeight(Math.max(600, Math.min(1200, available - 110)));\n}\n\nStreamlit.events.addEventListener(Streamlit.RENDER_EVENT, (event) => {\n  ready = true;\n  const reply = event.detail.args.response;\n  if (active && reply && reply.id === active.event.id) {\n    const completed = active;\n    active = null;\n    completed.cleanup();\n    if (!completed.cancelled) {\n      completed.resolve(new Response(JSON.stringify(reply.body), {\n        status: reply.status,\n        headers: { 'Content-Type': 'application/json' },\n      }));\n    }\n  }\n  resize();\n  pump();\n});\n\nwindow.fetch = function(input, init = {}) {\n  const raw = typeof input === 'string' ? input : input.url;\n  const url = new URL(raw, window.location.href);\n  const route = url.pathname;\n  if (url.origin !== window.location.origin ||\n      !['/api/health', '/api/ask'].includes(route)) {\n    return originalFetch(input, init);\n  }\n  const method = (init.method || input.method || 'GET').toUpperCase();\n  if ((route === '/api/health' && method !== 'GET') ||\n      (route === '/api/ask' && method !== 'POST')) {\n    return Promise.resolve(new Response(JSON.stringify({error:'Method not allowed.'}), {status:405}));\n  }\n  let body = null;\n  try {\n    body = init.body ? JSON.parse(init.body) : null;\n  } catch {\n    return Promise.resolve(new Response(JSON.stringify({error:'Invalid JSON.'}), {status:400}));\n  }\n  const signal = init.signal;\n  return new Promise((resolve, reject) => {\n    const item = {\n      event: {id: crypto.randomUUID(), action: route === '/api/ask' ? 'ask' : 'health', body},\n      resolve, reject, cancelled: false, cleanup: () => {},\n    };\n    const abort = () => {\n      item.cancelled = true;\n      item.cleanup();\n      reject(signal.reason || new DOMException('Request aborted', 'AbortError'));\n      pump();\n    };\n    if (signal?.aborted) { abort(); return; }\n    if (signal) {\n      signal.addEventListener('abort', abort, {once:true});\n      item.cleanup = () => signal.removeEventListener('abort', abort);\n    }\n    queue.push(item);\n    pump();\n  });\n};\n\nwindow.addEventListener('resize', resize);\nStreamlit.setComponentReady();\n// Match the supplied dark screenshot for first-time visitors; retain their choice.\ntry {\n  if (localStorage.getItem('saathi-dark') === null) {\n    localStorage.setItem('saathi-dark', 'true');\n  }\n} catch { /* The original React app also handles unavailable storage. */ }\n"

def install(root):
    root = Path(root).resolve()
    frontend = root / 'frontend'
    for required in ('src/main.jsx', 'src/style.css', 'index.html', 'package.json'):
        if not (frontend / required).is_file():
            raise RuntimeError('Missing frontend/' + required + '. Run beside app.py in your project.')
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise RuntimeError('Node.js/npm not found. Install Node.js, then reopen the terminal.')
    print('Building your ORIGINAL frontend for Streamlit. Keep this window open.', flush=True)
    with tempfile.TemporaryDirectory(prefix='scheme-saathi-ui-') as temporary:
        build = Path(temporary) / 'frontend'
        shutil.copytree(frontend, build, ignore=shutil.ignore_patterns('node_modules', 'dist', '.git'))
        # Work only on the temporary copy. Your frontend sources and lock stay intact.
        package = json.loads((build / 'package.json').read_text(encoding='utf-8'))
        package.setdefault('dependencies', {})['streamlit-component-lib'] = '2.0.0'
        package.setdefault('devDependencies', {}).update({'vite': '6.4.6', 'postcss': '8.5.33'})
        (build / 'package.json').write_text(json.dumps(package, indent=2), encoding='utf-8')
        (build / 'src/streamlit-bridge.js').write_text(BRIDGE, encoding='utf-8')
        html = (build / 'index.html').read_text(encoding='utf-8')
        marker = '<script type="module" src="/src/main.jsx"></script>'
        if marker not in html:
            raise RuntimeError('Unexpected frontend/index.html. No project files were changed.')
        html = html.replace(marker, '<script type="module" src="/src/streamlit-bridge.js"></script>' + marker)
        (build / 'index.html').write_text(html, encoding='utf-8')
        subprocess.run([npm, 'install', '--no-fund', '--no-audit'], cwd=build, check=True)
        subprocess.run([npm, 'run', 'build', '--', '--base', './'], cwd=build, check=True)
        output = build / 'dist'
        if not (output / 'index.html').is_file():
            raise RuntimeError('Frontend build did not produce index.html.')
        now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = root / '.scheme-saathi-backups' / ('original-ui-' + now)
        backup.mkdir(parents=True)
        destinations = ('streamlit_app.py', 'streamlit_ui', 'requirements.txt', '.gitignore')
        existed = {}
        for name in destinations:
            path = root / name
            existed[name] = path.exists()
            if path.is_dir():
                shutil.copytree(path, backup / name)
            elif path.is_file():
                shutil.copy2(path, backup / name)
        try:
            path = root / 'streamlit_ui'
            if path.exists():
                shutil.rmtree(path)
            shutil.copytree(output, path)
            (root / 'streamlit_app.py').write_text(APP, encoding='utf-8')
            reqpath = root / 'requirements.txt'
            requirements = reqpath.read_text(encoding='utf-8') if reqpath.exists() else ''
            lines = [line for line in requirements.splitlines() if not line.strip().lower().startswith('streamlit==')]
            lines.append('streamlit==1.51.0')
            reqpath.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            ignore = root / '.gitignore'
            content = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
            content += '\n# Keep credentials/backups private; commit compiled Streamlit component.\n'
            content += '.env\n.streamlit/secrets.toml\n/.scheme-saathi-backups/\n'
            content += '!streamlit_ui/\n!streamlit_ui/**\n'
            ignore.write_text(content, encoding='utf-8')
        except BaseException:
            for name in destinations:
                path = root / name
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                if existed[name]:
                    original = backup / name
                    if original.is_dir():
                        shutil.copytree(original, path)
                    else:
                        shutil.copy2(original, path)
            raise
    print('DONE. Original React interface is ready for Streamlit.')
    print('Backup:', backup)
    print('Your .env, frontend sources, documents and RAG index were preserved.')
    print('Test: python -X utf8 -m streamlit run streamlit_app.py')
    print('Upload: git add streamlit_app.py streamlit_ui requirements.txt .gitignore')
    print('Streamlit Cloud entry point stays streamlit_app.py. Keep API keys in Secrets.')


if __name__ == '__main__':
    try:
        install(Path(__file__).resolve().parent)
    except Exception as error:
        print('UPDATE FAILED:', error, file=sys.stderr)
        sys.exit(1)
