"""Read-only local UI preview backed by the deployed public JSON and media.

Only static public JSON is fetched. Media stays remote via HTTP redirects.
API endpoints are deliberately not proxied: even radar/pool GETs can collect
provider jobs and persist state. This server never sends mutations upstream.
"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, unquote
from urllib.request import Request, urlopen
from threading import Lock
import json
import time

ROOT = Path(__file__).resolve().parent
PUBLIC = 'https://character-lab-research.netlify.app'
STATIC_JSON = {'/data.json', '/characters.json'}
CACHE = {}
LOCK = Lock()

class Preview(BaseHTTPRequestHandler):
    def send(self, code, body=b'', mime='application/json; charset=utf-8', headers=None):
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def error_json(self, code, message):
        self.send(code, json.dumps({'error': message}, ensure_ascii=False).encode())

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if any(part in ('.', '..') for part in unquote(path).split('/')):
            return self.error_json(400, 'Invalid path')
        if path in ('/', '/index.html'):
            html = ROOT.joinpath('index.html').read_text()
            note = '<p class="local-preview-note" style="font-size:11px;color:var(--faint);margin:10px 0 0;line-height:1.5"><span class="fr">Aperçu local · données réelles</span><span class="en">Local preview · real data</span></p>'
            html = html.replace('<p class="note">Character Lab · Studio</p>', '<p class="note">Character Lab · Studio</p>'+note, 1)
            return self.send(200, html.encode(), 'text/html; charset=utf-8')
        if path in STATIC_JSON:
            with LOCK:
                cached = CACHE.get(path)
                if cached and time.monotonic() - cached[0] < 60:
                    raw = cached[1]
                else:
                    try:
                        req = Request(PUBLIC+path, headers={'Accept': 'application/json'})
                        with urlopen(req, timeout=25) as response:
                            raw = response.read()
                            json.loads(raw)
                        CACHE[path] = (time.monotonic(), raw)
                    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as err:
                        return self.error_json(502, 'Données publiques indisponibles / Public data unavailable')
            return self.send(200, raw, headers={'X-Preview-Data-Source': PUBLIC+path})
        if path.startswith(('/img/', '/clips/')):
            return self.send(302, headers={'Location': PUBLIC+path})
        if path.startswith(('/api/', '/.netlify/functions/')):
            return self.error_json(503, 'Aperçu local en lecture seule : ouvrez le site en ligne pour utiliser ce service. / Read-only local preview: open the live site to use this service.')
        if path == '/favicon.ico':
            return self.send(204, mime='image/x-icon')
        return self.error_json(404, 'Not found')

    do_HEAD = do_GET

    def do_POST(self):
        self.error_json(405, 'Aperçu local en lecture seule / Read-only local preview')

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def log_message(self, *args):
        pass

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4176)
    args = parser.parse_args()
    print(f'Character Lab preview: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Preview).serve_forever()
