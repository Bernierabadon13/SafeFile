"""SafeFile Mini Cloud: a tiny self-hosted backup server (standard library only, free to run).

Run it on any computer (another PC, an old laptop, a Raspberry Pi) so backups leave your main machine:

    python -m safepoint.engine.minicloud --root D:\\MiniCloud --token YOUR_SECRET --host 0.0.0.0 --port 8765

SafeFile can also run one inside the app, bound to this PC only (127.0.0.1).
Traffic is plain HTTP and the token is the only protection: use it on localhost or a trusted network.
"""
from __future__ import annotations

import argparse
import hmac
import json
import secrets
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .errors import HashMismatch, StoreError
from .stores import CHUNK, LocalStore, valid_key, valid_sha

MAX_NAMED = 32 * 1024 * 1024


class _Handler(BaseHTTPRequestHandler):
    server_version = "SafeFileMiniCloud/1"

    def log_message(self, *args):  # keep the console quiet
        pass

    # ---- helpers
    @property
    def store(self) -> LocalStore:
        return self.server.store

    def _send(self, status, payload=None, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps(payload if payload is not None else {}).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, status, msg):
        self._send(status, {"error": msg})

    def _authorised(self):
        sent = self.headers.get("Authorization", "")
        ok = sent.startswith("Bearer ") and hmac.compare_digest(sent[7:], self.server.token)
        if not ok:
            self._err(401, "unauthorised")
        return ok

    def _route(self):
        u = urlsplit(self.path)
        return [unquote(p) for p in u.path.split("/") if p], parse_qs(u.query)

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_NAMED:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(length) or b"{}")

    # ---- verbs
    def do_GET(self):
        if not self._authorised():
            return
        parts, q = self._route()
        try:
            if parts == ["v1", "ping"]:
                try:
                    free = shutil.disk_usage(self.store.root).free
                except OSError:
                    free = None
                self._send(200, {"service": "safefile-minicloud", "version": 1, "free_bytes": free})
            elif parts == ["v1", "list"]:
                self._send(200, {"blobs": [[s, m] for s, m in self.store.list_blobs()]})
            elif len(parts) == 3 and parts[:2] == ["v1", "blob"] and valid_sha(parts[2]):
                path = self.store._obj(parts[2])
                if not path.is_file():
                    return self._err(404, "not found")
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(path.stat().st_size))
                self.end_headers()
                with open(path, "rb") as f:
                    while True:
                        block = f.read(CHUNK)
                        if not block:
                            break
                        self.wfile.write(block)
            elif parts == ["v1", "named"]:
                key = (q.get("key") or [""])[0]
                if not valid_key(key):
                    return self._err(400, "bad key")
                data = self.store.get_named(key)
                if data is None:
                    return self._err(404, "not found")
                self._send(200, raw=data, ctype="application/octet-stream")
            else:
                self._err(404, "unknown endpoint")
        except (BrokenPipeError, ConnectionError):
            pass
        except StoreError as err:
            self._err(500, str(err))

    def do_POST(self):
        if not self._authorised():
            return
        parts, _q = self._route()
        try:
            body = self._json_body()
            shas = [s for s in body.get("shas", []) if valid_sha(s)]
            if parts == ["v1", "have"]:
                self._send(200, {"have": sorted(self.store.has_blobs(shas))})
            elif parts == ["v1", "verify"]:
                bad, missing = self.store.verify_blobs(shas)
                self._send(200, {"bad": bad, "missing": missing})
            else:
                self._err(404, "unknown endpoint")
        except (ValueError, KeyError):
            self._err(400, "bad request")
        except (BrokenPipeError, ConnectionError):
            pass

    def do_PUT(self):
        if not self._authorised():
            return
        parts, q = self._route()
        length = int(self.headers.get("Content-Length") or 0)
        try:
            if len(parts) == 3 and parts[:2] == ["v1", "blob"] and valid_sha(parts[2]):
                def chunks():
                    left = length
                    while left > 0:
                        block = self.rfile.read(min(CHUNK, left))
                        if not block:
                            return
                        left -= len(block)
                        yield block
                try:
                    self.store.put_stream(parts[2], chunks())
                except HashMismatch:
                    return self._err(400, "hash mismatch")
                self._send(200, {"ok": True})
            elif parts == ["v1", "named"]:
                key = (q.get("key") or [""])[0]
                if not valid_key(key) or length > MAX_NAMED:
                    return self._err(400, "bad key or size")
                self.store.put_named(key, self.rfile.read(length))
                self._send(200, {"ok": True})
            else:
                self._err(404, "unknown endpoint")
        except (BrokenPipeError, ConnectionError):
            pass
        except StoreError as err:
            self._err(500, str(err))

    def do_DELETE(self):
        if not self._authorised():
            return
        parts, q = self._route()
        try:
            if len(parts) == 3 and parts[:2] == ["v1", "blob"] and valid_sha(parts[2]):
                self.store.delete_blob(parts[2])
                self._send(200, {"ok": True})
            elif parts == ["v1", "named"]:
                key = (q.get("key") or [""])[0]
                if not valid_key(key):
                    return self._err(400, "bad key")
                self.store.delete_named(key)
                self._send(200, {"ok": True})
            else:
                self._err(404, "unknown endpoint")
        except StoreError as err:
            self._err(500, str(err))


class _Httpd(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MiniCloudServer:
    def __init__(self, root, token, host="127.0.0.1", port=8765):
        if not token:
            raise StoreError("Mini Cloud needs an access token.")
        self.root, self.token, self.host, self.port = Path(root), token, host, port
        self.httpd = None
        self._thread = None

    def start(self):
        store = LocalStore(self.root)
        store.check()
        try:
            self.httpd = _Httpd((self.host, self.port), _Handler)
        except OSError as err:
            raise StoreError(f"Mini Cloud could not start on port {self.port}: {err.strerror or err}") from err
        self.httpd.store, self.httpd.token = store, self.token
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="minicloud", daemon=True)
        self._thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="SafeFile Mini Cloud server")
    ap.add_argument("--root", required=True, help="folder where backups are stored")
    ap.add_argument("--token", help="access token (generated and printed if omitted)")
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to accept other devices on your network")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    token = args.token or secrets.token_urlsafe(24)
    server = MiniCloudServer(args.root, token, args.host, args.port)
    server.start()
    print(f"SafeFile Mini Cloud running at {server.url}")
    print(f"Storage folder: {Path(args.root).resolve()}")
    print(f"Access token:   {token}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
