from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(path: str | Path | None = None) -> None:
        if not path:
            return
        dotenv_path = Path(path)
        if not dotenv_path.exists():
            return
        for raw_line in dotenv_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

load_dotenv(ROOT / '.env')
HOST = os.getenv('ADMIN_SERVER_HOST', '127.0.0.1')
PORT = int(os.getenv('ADMIN_SERVER_PORT', '8001'))
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', '') or SUPABASE_SERVICE_ROLE_KEY
SCRAPER_PATH = ROOT / 'scraper.py'
IMAGES_DIR = ROOT / 'images'

# Ensure images directory exists
IMAGES_DIR.mkdir(exist_ok=True)


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-File-Name')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.end_headers()
    handler.wfile.write(body)


def auth_user(access_token: str) -> dict:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError('Missing SUPABASE_URL or SUPABASE_ANON_KEY')

    req = Request(
        SUPABASE_URL.rstrip('/') + '/auth/v1/user',
        headers={
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        },
        method='GET',
    )
    try:
        with urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
            print(f'auth_user ok: user_id={payload.get("id")}, email={payload.get("email")}')
            return payload
    except HTTPError as exc:
        body = ''
        try:
            body = exc.read().decode('utf-8', errors='replace')
        except Exception:
            body = '<unreadable body>'
        print(f'auth_user HTTPError: code={exc.code} reason={exc.reason} body={body}')
        raise


def is_admin(user_id: str, access_token: str) -> bool:
    endpoint = SUPABASE_URL.rstrip('/') + f"/rest/v1/admin_users?select=user_id&user_id=eq.{user_id}&limit=1"
    req = Request(
        endpoint,
        headers={
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        },
        method='GET',
    )
    try:
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f'is_admin ok: user_id={user_id}, rows={len(data) if isinstance(data, list) else "n/a"}')
            return bool(data)
    except HTTPError as exc:
        body = ''
        try:
            body = exc.read().decode('utf-8', errors='replace')
        except Exception:
            body = '<unreadable body>'
        print(f'is_admin HTTPError: user_id={user_id} code={exc.code} reason={exc.reason} body={body}')
        raise


def run_scraper(query: str, mode: str, max_new: int | None) -> tuple[int, dict]:
    cmd = [sys.executable, str(SCRAPER_PATH), query, '--mode', mode]
    if max_new:
        cmd += ['--max-new', str(max_new)]

    env = os.environ.copy()
    env['SUPABASE_URL'] = SUPABASE_URL
    env['SUPABASE_SERVICE_ROLE_KEY'] = SUPABASE_SERVICE_ROLE_KEY

    google_places_key = os.getenv('GOOGLE_PLACES_API_KEY') or os.getenv('PLACES_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    if google_places_key:
        env['GOOGLE_PLACES_API_KEY'] = google_places_key
        env['PLACES_API_KEY'] = google_places_key
    else:
        env.pop('GOOGLE_PLACES_API_KEY', None)
        env.pop('PLACES_API_KEY', None)
    if gemini_key:
        env['GEMINI_API_KEY'] = gemini_key
    else:
        env.pop('GEMINI_API_KEY', None)

    print('run_scraper env presence:', {
        'SUPABASE_URL': bool(env.get('SUPABASE_URL')),
        'SUPABASE_SERVICE_ROLE_KEY': bool(env.get('SUPABASE_SERVICE_ROLE_KEY')),
        'GOOGLE_PLACES_API_KEY': bool(env.get('GOOGLE_PLACES_API_KEY')),
        'PLACES_API_KEY': bool(env.get('PLACES_API_KEY')),
        'GEMINI_API_KEY': bool(env.get('GEMINI_API_KEY')),
    })

    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60 * 30,
    )
    return proc.returncode, {'output': proc.stdout}


class AdminHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        rel = parsed.path.lstrip('/')
        if rel == '' or rel == 'admin.html':
            rel = 'admin.html'
        if rel == 'api/admin/run-scraper':
            return str(ROOT)
        return str((ROOT / rel).resolve())

    def end_headers(self) -> None:
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-File-Name')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == '/api/admin/run-scraper':
            json_response(self, HTTPStatus.METHOD_NOT_ALLOWED, {'error': 'Use POST'})
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == '/api/admin/upload-image':
            self.handle_upload_image()
            return
            
        if parsed.path != '/api/admin/run-scraper':
            json_response(self, HTTPStatus.NOT_FOUND, {'error': 'Not found'})
            return

        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            json_response(self, HTTPStatus.UNAUTHORIZED, {'error': 'Missing bearer token'})
            return

        access_token = auth_header.split(' ', 1)[1].strip()
        try:
            user = auth_user(access_token)
            print(f'run_scraper auth user id={user.get("id")} email={user.get("email")}')
            if not is_admin(user['id'], access_token):
                print(f'run_scraper denied: not admin user_id={user.get("id")}')
                json_response(self, HTTPStatus.FORBIDDEN, {'error': 'Not an admin user'})
                return
        except HTTPError as exc:
            status = HTTPStatus.UNAUTHORIZED if exc.code == 401 else HTTPStatus.FORBIDDEN if exc.code == 403 else HTTPStatus.BAD_GATEWAY
            print(f'run_scraper HTTPError during auth: code={exc.code} reason={exc.reason}')
            json_response(self, status, {'error': f'Auth error: {exc}'})
            return
        except (URLError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
            print(f'run_scraper auth verification failed: {type(exc).__name__}: {exc}')
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {'error': f'Auth verification failed: {exc}'})
            return

        length = int(self.headers.get('Content-Length', '0') or '0')
        raw = self.rfile.read(length) if length else b'{}'
        try:
            body = json.loads(raw.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            body = {}

        query = str(body.get('query') or 'Melbourne coffee')
        mode = str(body.get('mode') or 'rest')
        max_new = body.get('maxNew')
        try:
            max_new_int = int(max_new) if max_new not in (None, '', 0, '0') else None
        except (TypeError, ValueError):
            max_new_int = None

        # Start streaming response
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

        cmd = [sys.executable, str(SCRAPER_PATH), query, '--mode', mode]
        if max_new_int:
            cmd += ['--max-new', str(max_new_int)]

        env = os.environ.copy()
        env['SUPABASE_URL'] = SUPABASE_URL
        env['SUPABASE_SERVICE_ROLE_KEY'] = SUPABASE_SERVICE_ROLE_KEY
        
        google_places_key = os.getenv('GOOGLE_PLACES_API_KEY') or os.getenv('PLACES_API_KEY')
        gemini_key = os.getenv('GEMINI_API_KEY')
        if google_places_key:
            env['GOOGLE_PLACES_API_KEY'] = google_places_key
            env['PLACES_API_KEY'] = google_places_key
        if gemini_key:
            env['GEMINI_API_KEY'] = gemini_key

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            for line in process.stdout:
                self.wfile.write(line.encode('utf-8'))
                self.wfile.flush()
            
            process.wait()
            if process.returncode != 0:
                self.wfile.write(f"\n[ERROR] Scraper exited with code {process.returncode}\n".encode('utf-8'))
            else:
                self.wfile.write(b"\n[SUCCESS] Scraper finished successfully.\n")
            self.wfile.flush()

        except Exception as exc:
            msg = f"\n[ERROR] Failed to execute scraper: {exc}\n"
            self.wfile.write(msg.encode('utf-8'))
            self.wfile.flush()

    def handle_upload_image(self) -> None:
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            json_response(self, HTTPStatus.UNAUTHORIZED, {'error': 'Missing bearer token'})
            return

        access_token = auth_header.split(' ', 1)[1].strip()
        try:
            user = auth_user(access_token)
            if not is_admin(user['id'], access_token):
                json_response(self, HTTPStatus.FORBIDDEN, {'error': 'Not an admin user'})
                return
        except Exception as exc:
            print(f"Auth verification failed: {exc}")
            json_response(self, HTTPStatus.UNAUTHORIZED, {'error': f'Auth failed: {exc}'})
            return

        print(f"Handling image upload. Headers: {dict(self.headers)}")

        # Simple file capture from raw body
        # We expect X-File-Name header and raw binary content
        filename = self.headers.get('X-File-Name', f'upload_{int(time.time())}.jpg')
        # Clean filename to prevent traversal
        safe_filename = "".join([c for c in filename if c.isalnum() or c in '._-']).strip()
        if not safe_filename:
            safe_filename = "unnamed_image.jpg"
            
        target_path = IMAGES_DIR / safe_filename
        
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0:
            json_response(self, HTTPStatus.BAD_REQUEST, {'error': 'Empty file content'})
            return
            
        try:
            with open(target_path, 'wb') as f:
                f.write(self.rfile.read(length))
            
            # Return the relative path from ROOT point of view
            # Since 8000 port serves ROOT, the URL will be /images/filename
            json_response(self, HTTPStatus.OK, {
                'url': f'/images/{safe_filename}',
                'path': str(target_path.relative_to(ROOT))
            })
            print(f"Image uploaded successfully: {safe_filename}")
        except Exception as exc:
            print(f"Failed to save image: {exc}")
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {'error': f'Save failed: {exc}'})


if __name__ == '__main__':
    print(
        'ENV CHECK:',
        {
            'SUPABASE_URL': bool(SUPABASE_URL),
            'SUPABASE_ANON_KEY': bool(SUPABASE_ANON_KEY),
            'SUPABASE_SERVICE_ROLE_KEY': bool(SUPABASE_SERVICE_ROLE_KEY),
        },
    )
    if not SUPABASE_URL or not SUPABASE_ANON_KEY or not SUPABASE_SERVICE_ROLE_KEY:
        print('WARNING: SUPABASE_URL, SUPABASE_ANON_KEY, or SUPABASE_SERVICE_ROLE_KEY is missing; scraper endpoint may not work.')
    mimetypes.init()
    server = ThreadingHTTPServer((HOST, PORT), AdminHandler)
    print(f'Serving {ROOT} at http://{HOST}:{PORT}')
    server.serve_forever()
