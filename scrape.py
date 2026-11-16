"""Conservative allowlisted public-source collector. Fail closed on robots errors."""
import argparse
import hashlib
import ipaddress
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
AGENT = 'SchemeSaathi/1.0'
ALLOWED = {'scholarships.gov.in', 'www.education.gov.in', 'www.aicte-india.org',
           'www.myscheme.gov.in', 'sje.rajasthan.gov.in', 'www.megeducation.gov.in', 'www.dtekerala.gov.in', 'sarswati.aicte.gov.in'}
_last = {}

def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED or parsed.port not in (None, 443) or parsed.username:
        raise ValueError('Only explicitly allowlisted HTTPS government hosts are permitted')
    return parsed

def get(url):
    validate_url(url)
    # Validate every redirect before making the next request.
    for _ in range(6):
        response = requests.get(url, headers={'User-Agent': AGENT}, timeout=30,
                                allow_redirects=False, stream=True)
        if response.is_redirect:
            url = urljoin(url, response.headers['Location'])
            response.close()
            validate_url(url)
            continue
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > 20 * 1024 * 1024:
                response.close()
                raise ValueError('Source exceeds 20 MB limit')
        response.close()
        return bytes(body), url
    raise ValueError('Too many redirects')

def collect(url, status='unverified', document_date=None, title=None, applicable_from=None, include_pages=None):
    parsed = validate_url(url)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    try:
        robot_body, _ = get(origin + '/robots.txt')
        robots_status = 'retrieved'
    except requests.HTTPError as error:
        if error.response.status_code not in (404, 410):
            raise
        # RFC 9309 section 2.3.1.3: unavailable (4xx) robots permits access.
        # Be stricter for 401/403/429; only 404/410 are accepted here.
        robot_body = b'User-agent: *\nAllow: /'
        robots_status = 'absent_404_or_410' 
    if b'<html' in robot_body.lower() or b'<!doctype html' in robot_body.lower():
        raise ValueError('robots.txt returned HTML instead of robots rules; collection skipped')
    robot = RobotFileParser()
    robot.parse(robot_body.decode('utf-8', errors='replace').splitlines())
    if not robot.can_fetch(AGENT, url):
        raise ValueError('robots.txt disallows collection')
    delay = max(2, robot.crawl_delay(AGENT) or robot.crawl_delay('*') or 0)
    time.sleep(max(0, delay - (time.monotonic() - _last.get(origin, 0))))
    _last[origin] = time.monotonic()
    body, final_url = get(url)
    stamp = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(body).hexdigest()
    (ROOT / 'data/pdfs').mkdir(parents=True, exist_ok=True)
    (ROOT / 'data/scraped').mkdir(parents=True, exist_ok=True)
    metadata = {'url': final_url, 'requested_url': url, 'last_scraped': stamp,
                'sha256': digest, 'status': status, 'document_date': document_date, 'robots_status': robots_status, 'applicable_from': applicable_from, 'include_pages': include_pages}
    if body.startswith(b'%PDF'):
        name = digest[:12] + '.pdf'
        (ROOT / 'data/pdfs' / name).write_bytes(body)
        metadata.update(source=name, title=title or urlparse(final_url).path.split('/')[-1])
        (ROOT / 'data/pdfs' / (name + '.json')).write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    else:
        soup = BeautifulSoup(body, 'html.parser')
        title = title or (soup.title.get_text(' ', strip=True) if soup.title else final_url)
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        main = soup.find('main') or soup.body or soup
        text = main.get_text(' ', strip=True)
        if len(text.split()) < 50:
            raise ValueError('No sufficient readable content; page may require JavaScript')
        name = digest[:12] + '.json'
        metadata.update(source=name, title=title, text=text)
        (ROOT / 'data/scraped' / name).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('urls', nargs='*')
    parser.add_argument('--manifest', default=None)
    args = parser.parse_args()
    targets = json.loads(Path(args.manifest).read_text(encoding='utf-8')) if args.manifest else [{'url': u} for u in args.urls]
    report = []
    for target in targets:
        try:
            report.append({'ok': True, **collect(**target)})
        except Exception as error:
            report.append({'ok': False, 'url': target['url'], 'error': str(error)})
    (ROOT / 'data/collection_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
