"""Loopback-only owner console. No external client or production web deployment."""
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

from . import control as service
from .contracts import GuardError, canonical, exact, require
from .engine import Engine

ASSETS = Path(__file__).with_name('web')
MAX_BODY = 2 * 1024 * 1024


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = True

    def __init__(self, engine, port=8765):
        # Validate owner/schema before opening a listener. Bind address is not configurable.
        with engine.store.transaction():
            pass
        self.engine = engine
        self.login_code = secrets.token_urlsafe(24)
        self.login_expires = time.monotonic()+600
        self.failures = 0
        self.sessions = {}
        self.auth_lock = threading.Lock()
        super().__init__(('127.0.0.1', port), ConsoleHandler)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.cookie_name = f'dg_session_{self.server_port}'


class ConsoleHandler(BaseHTTPRequestHandler):
    server_version = 'DecisionGuard'

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass  # No requests, documents, cookies or login code in HTTP logs.

    def send_error(self, code, message=None, explain=None):
        self.reply(code, {'error':'http_error', 'message':'Unsupported HTTP request.'})

    def reply(self, status, data, content_type='application/json; charset=utf-8', cookie=None):
        raw = data if isinstance(data, bytes) else canonical(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.send_header('Connection', 'close')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def boundary(self, write=False):
        if self.headers.get_all('Host', []) != [self.server.origin.removeprefix('http://')]:
            raise GuardError('forbidden', 'Open the exact 127.0.0.1 URL printed in the terminal.')
        origin = self.headers.get_all('Origin', [])
        if (write and origin != [self.server.origin]) or (origin and origin != [self.server.origin]):
            raise GuardError('forbidden', 'Cross-origin requests are not accepted.')
        if self.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site'):
            raise GuardError('forbidden', 'Use the console directly on its own origin.')

    def session(self):
        cookies = SimpleCookie()
        cookies.load(self.headers.get('Cookie', ''))
        morsel = cookies.get(self.server.cookie_name)
        token = morsel.value if morsel else ''
        with self.server.auth_lock:
            item = self.server.sessions.get(token)
            if item is None or item['expires'] <= time.monotonic():
                self.server.sessions.pop(token, None)
                raise GuardError('unauthorized', 'Unlock the console using the code from its terminal. Restart the console if the code has expired or was already used.')
        return token, item

    def body(self):
        require(self.headers.get('Content-Type') == 'application/json', 'Send application/json.')
        require(not self.headers.get_all('Transfer-Encoding'), 'Transfer encoding is not supported.')
        lengths = self.headers.get_all('Content-Length', [])
        require(len(lengths) == 1 and lengths[0].isdigit(), 'One content length is required.')
        length = int(lengths[0])
        require(0 < length <= MAX_BODY, 'Request must be at most 2 MiB.')
        raw = self.rfile.read(length)
        require(len(raw) == length, 'Incomplete request body.')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'Duplicate JSON fields are not allowed.')
                result[key] = value
            return result
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))

    def do_GET(self):
        self.handle_call(False)

    def do_POST(self):
        self.handle_call(True)

    def handle_call(self, write):
        try:
            self.boundary(write)
            parsed = urlsplit(self.path)
            require(not parsed.scheme and not parsed.netloc and not parsed.fragment, 'Invalid request target.')
            path = parsed.path
            if not write and path in ('/', '/app.js', '/style.css'):
                name, mime = {'/':('index.html','text/html'), '/app.js':('app.js','text/javascript'), '/style.css':('style.css','text/css')}[path]
                return self.reply(200, (ASSETS/name).read_bytes(), mime+'; charset=utf-8')
            if write and path == '/api/login':
                data = self.body(); exact(data, {'code'})
                code = data['code']
                with self.server.auth_lock:
                    valid = isinstance(code, str) and code.isascii() and self.server.login_code and self.server.failures < 10 and time.monotonic() < self.server.login_expires and secrets.compare_digest(code, self.server.login_code)
                    if not valid:
                        self.server.failures += 1
                        raise GuardError('unauthorized', 'Invalid or expired code. After 10 attempts, restart the console for a new code.')
                    self.server.login_code = None
                    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                    self.server.sessions[token] = {'csrf':csrf, 'expires':time.monotonic()+28800}
                return self.reply(200, {'csrf':csrf}, cookie=f'{self.server.cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            token, session = self.session()
            if write:
                csrf = self.headers.get('X-DG-CSRF', '')
                if not csrf.isascii() or not secrets.compare_digest(csrf, session['csrf']):
                    raise GuardError('forbidden', 'Refresh the console before submitting an owner action.')
                data = self.body()
                if path == '/api/logout':
                    exact(data, set())
                    with self.server.auth_lock:
                        self.server.sessions.pop(token, None)
                    return self.reply(200, {'logged_out':True}, cookie=f'{self.server.cookie_name}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if path.startswith('/api/admin/'):
                    return self.reply(200, service.mutate(self.server.engine, path.removeprefix('/api/admin/'), data))
            else:
                query = parse_qs(parsed.query, strict_parsing=True)
                def param(name, default=''):
                    require(set(query) <= {name} and len(query.get(name, [default])) == 1, 'Invalid query parameters.')
                    return query.get(name, [default])[0]
                if path == '/api/session':
                    return self.reply(200, {'csrf':session['csrf']})
                if path == '/api/snapshot':
                    return self.reply(200, service.snapshot(self.server.engine))
                if path == '/api/events':
                    return self.reply(200, service.timeline(self.server.engine, int(param('before','0'))))
                if path == '/api/graph':
                    return self.reply(200, service.graph(self.server.engine, param('task')))
                if path == '/api/action':
                    return self.reply(200, service.action_detail(self.server.engine, param('id')))
            self.reply(404, {'error':'not_found', 'message':'Unknown console route.'})
        except GuardError as error:
            status = {'unauthorized':401, 'forbidden':403, 'store_unavailable':503, 'schema_mismatch':503, 'owner_required':403}.get(error.code, 400)
            self.reply(status, {'error':error.code, 'message':str(error)})
        except (ValueError, UnicodeError, RecursionError, TypeError):
            self.reply(400, {'error':'invalid_input', 'message':'Malformed input. Refresh state before trying again.'})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass  # Caller must reconcile: committed effects may precede a lost response.
        except Exception:
            self.reply(500, {'error':'unknown_outcome', 'message':'Request failed. Refresh and inspect events and receipts before retrying; an effect may have committed.'})


def serve(path, port=8765):
    require(type(port) is int and 0 <= port <= 65535, 'Invalid port.')
    with ConsoleServer(Engine(path), port) as server:
        print(f'DecisionGuard owner console: {server.origin}', flush=True)
        print(f'One-use local unlock code (valid 10 minutes): {server.login_code}', flush=True)
        print('No external API key is needed. Keep this terminal private. Ctrl+C stops the console.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
