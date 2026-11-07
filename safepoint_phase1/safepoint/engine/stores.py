"""Backup destinations. Both stores expose the same interface:

    check(), has_blobs(), put_blob(), read_blob(), verify_blobs(), list_blobs(), delete_blob(),
    put_named(), get_named(), delete_named()

`LocalStore` writes to a folder (any partition, external drive or synced folder).
`CloudStore` talks to a Mini Cloud server (see minicloud.py) over HTTP(S).
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit

from .core import CHUNK, sha256_file
from .errors import Cancelled, HashMismatch, SafeFileError, SourceChanged, StoreError

import hashlib

_SHA = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9._\-/]+$")


def valid_sha(s: str) -> bool:
    return bool(_SHA.match(s or ""))


def valid_key(key: str) -> bool:
    return bool(_KEY.match(key or "")) and not key.startswith("/") and ".." not in key.split("/")


def _file_chunks(path, expected_size):
    total = 0
    try:
        with open(path, "rb") as f:
            while True:
                block = f.read(CHUNK)
                if not block:
                    break
                total += len(block)
                yield block
    except OSError as err:
        raise SourceChanged(err.strerror or str(err)) from err
    if total != expected_size:
        raise SourceChanged("file size changed while reading")


# ================================================================== local
class LocalStore:
    kind = "local"

    def __init__(self, root, store_id=None):
        self.root = Path(root)
        self.id = store_id or f"local:{self.root}"
        self.label = "Local storage"
        self.local_root = str(self.root)

    def _obj(self, sha):
        return self.root / "objects" / sha[:2] / sha

    def _named(self, key):
        if not valid_key(key):
            raise StoreError(f"Invalid key: {key}")
        return self.root / key

    def check(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / f".probe-{os.getpid()}"
            probe.write_bytes(b"ok")
            probe.unlink()
        except OSError as err:
            raise StoreError(f"Cannot write to {self.root}: {err.strerror or err}") from err

    def free_bytes(self):
        try:
            return shutil.disk_usage(self.root if self.root.exists() else self.root.anchor or ".").free
        except OSError:
            return None

    def has_blobs(self, shas):
        return {s for s in shas if self._obj(s).is_file()}

    def put_stream(self, sha, chunks):
        """Store data under `sha`. Raises HashMismatch (and stores nothing) if it does not match."""
        if not valid_sha(sha):
            raise StoreError("Invalid blob id")
        dest = self._obj(sha)
        tmp_dir = self.root / "tmp"
        try:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=tmp_dir)
        except OSError as err:
            raise StoreError(f"Cannot write to {self.root}: {err.strerror or err}") from err
        h = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as out:
                for block in chunks:
                    h.update(block)
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
            if h.hexdigest() != sha:
                raise HashMismatch("content does not match its hash")
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, dest)
        except OSError as err:
            raise StoreError(f"Write failed in {self.root}: {err.strerror or err}") from err
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def put_blob(self, sha, path, size):
        try:
            self.put_stream(sha, _file_chunks(path, size))
        except HashMismatch as err:
            raise SourceChanged("file changed while it was being copied") from err

    def read_blob(self, sha):
        try:
            with open(self._obj(sha), "rb") as f:
                while True:
                    block = f.read(CHUNK)
                    if not block:
                        return
                    yield block
        except FileNotFoundError as err:
            raise StoreError("blob is missing from the destination") from err
        except OSError as err:
            raise StoreError(err.strerror or str(err)) from err

    def verify_blobs(self, shas, on_progress=None, cancel=None):
        bad, missing = [], []
        for i, s in enumerate(shas):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            p = self._obj(s)
            if not p.is_file():
                missing.append(s)
            else:
                try:
                    if sha256_file(p, cancel=cancel) != s:
                        bad.append(s)
                except OSError:
                    bad.append(s)
            if on_progress:
                on_progress(i + 1, len(shas))
        return bad, missing

    def list_blobs(self):
        base = self.root / "objects"
        if not base.is_dir():
            return
        for sub in base.iterdir():
            if sub.is_dir():
                for f in sub.iterdir():
                    if valid_sha(f.name):
                        try:
                            yield f.name, f.stat().st_mtime
                        except OSError:
                            continue

    def delete_blob(self, sha):
        try:
            self._obj(sha).unlink()
        except FileNotFoundError:
            pass
        except OSError as err:
            raise StoreError(err.strerror or str(err)) from err

    def put_named(self, key, data: bytes):
        path = self._named(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".part")
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError as err:
            raise StoreError(f"Write failed in {self.root}: {err.strerror or err}") from err

    def get_named(self, key):
        try:
            return self._named(key).read_bytes()
        except FileNotFoundError:
            return None
        except OSError as err:
            raise StoreError(err.strerror or str(err)) from err

    def delete_named(self, key):
        try:
            self._named(key).unlink()
        except FileNotFoundError:
            pass
        except OSError as err:
            raise StoreError(err.strerror or str(err)) from err


# ================================================================== cloud
class _Limited:
    """File wrapper that yields exactly `size` bytes (http.client reads it until b'')."""

    def __init__(self, f, size):
        self.f, self.left = f, size

    def read(self, n=-1):
        if self.left <= 0:
            return b""
        n = self.left if (n is None or n < 0) else min(n, self.left)
        try:
            block = self.f.read(n)
        except OSError as err:
            raise SourceChanged(err.strerror or str(err)) from err
        if not block:
            raise SourceChanged("file shrank while uploading")
        self.left -= len(block)
        return block


class CloudStore:
    kind = "cloud"

    def __init__(self, url, token, store_id=None, label="Mini Cloud", local_root=None, timeout=60):
        self.url = url.rstrip("/")
        parts = urlsplit(self.url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise StoreError("The Mini Cloud address must look like http://host:8765")
        self._https = parts.scheme == "https"
        self._host, self._port = parts.hostname, parts.port or (443 if self._https else 80)
        self.token = token
        self.id = store_id or f"cloud:{self.url}"
        self.label = label
        self.local_root = local_root
        self.timeout = timeout

    # ---- plumbing
    def _conn(self, timeout=None):
        cls = http.client.HTTPSConnection if self._https else http.client.HTTPConnection
        conn = cls(self._host, self._port, timeout=timeout or self.timeout)
        conn.blocksize = CHUNK
        return conn

    def _headers(self, extra=None):
        h = {"Authorization": f"Bearer {self.token}"}
        h.update(extra or {})
        return h

    def _fail(self, status, data=b""):
        if status == 401:
            raise StoreError("Mini Cloud rejected the access token")
        detail = ""
        try:
            detail = json.loads(data.decode("utf-8")).get("error", "")
        except Exception:
            pass
        raise StoreError(f"Mini Cloud error {status}" + (f": {detail}" if detail else ""))

    def _call(self, method, path, body=None, headers=None, timeout=None):
        conn = self._conn(timeout)
        try:
            conn.request(method, path, body=body, headers=self._headers(headers))
            resp = conn.getresponse()
            return resp.status, resp.read()
        except (OSError, http.client.HTTPException) as err:
            raise StoreError(f"Mini Cloud is not reachable at {self.url} ({err})") from err
        finally:
            conn.close()

    def _json(self, method, path, payload=None, timeout=None):
        body = json.dumps(payload).encode() if payload is not None else None
        status, data = self._call(method, path, body, {"Content-Type": "application/json"}, timeout)
        if status != 200:
            self._fail(status, data)
        return json.loads(data.decode("utf-8"))

    # ---- interface
    def check(self):
        info = self._json("GET", "/v1/ping")
        if info.get("service") != "safefile-minicloud":
            raise StoreError(f"{self.url} is not a SafeFile Mini Cloud")
        return info

    def free_bytes(self):
        try:
            return self._json("GET", "/v1/ping").get("free_bytes")
        except SafeFileError:
            return None

    def has_blobs(self, shas):
        shas, found = list(shas), set()
        for i in range(0, len(shas), 2000):
            found.update(self._json("POST", "/v1/have", {"shas": shas[i:i + 2000]}).get("have", []))
        return found

    def put_blob(self, sha, path, size):
        last = None
        for _attempt in (1, 2):
            conn = self._conn(timeout=300)
            try:
                with open(path, "rb") as f:
                    conn.request("PUT", f"/v1/blob/{sha}", body=_Limited(f, size),
                                 headers=self._headers({"Content-Length": str(size),
                                                        "Content-Type": "application/octet-stream"}))
                    resp = conn.getresponse()
                    data = resp.read()
                if resp.status in (200, 201):
                    return
                if resp.status == 400:
                    raise SourceChanged("file changed while it was being uploaded")
                self._fail(resp.status, data)
            except SafeFileError:
                raise
            except OSError as err:
                last = err
            except http.client.HTTPException as err:
                last = err
            finally:
                conn.close()
        raise StoreError(f"Mini Cloud is not reachable at {self.url} ({last})")

    def read_blob(self, sha):
        conn = self._conn(timeout=300)
        try:
            conn.request("GET", f"/v1/blob/{sha}", headers=self._headers())
            resp = conn.getresponse()
            if resp.status == 404:
                raise StoreError("blob is missing from the Mini Cloud")
            if resp.status != 200:
                self._fail(resp.status, resp.read())
            while True:
                block = resp.read(CHUNK)
                if not block:
                    return
                yield block
        except (OSError, http.client.HTTPException) as err:
            raise StoreError(f"Mini Cloud connection failed ({err})") from err
        finally:
            conn.close()

    def verify_blobs(self, shas, on_progress=None, cancel=None):
        """The server re-reads and re-hashes each blob itself (no download needed)."""
        shas, bad, missing = list(shas), [], []
        for i in range(0, len(shas), 20):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            r = self._json("POST", "/v1/verify", {"shas": shas[i:i + 20]}, timeout=1800)
            bad += r.get("bad", [])
            missing += r.get("missing", [])
            if on_progress:
                on_progress(min(i + 20, len(shas)), len(shas))
        return bad, missing

    def list_blobs(self):
        for sha, mtime in self._json("GET", "/v1/list", timeout=300).get("blobs", []):
            yield sha, mtime

    def delete_blob(self, sha):
        status, data = self._call("DELETE", f"/v1/blob/{sha}")
        if status not in (200, 404):
            self._fail(status, data)

    def put_named(self, key, data: bytes):
        status, resp = self._call("PUT", f"/v1/named?key={quote(key, safe='')}", data,
                                  {"Content-Type": "application/octet-stream"})
        if status != 200:
            self._fail(status, resp)

    def get_named(self, key):
        status, data = self._call("GET", f"/v1/named?key={quote(key, safe='')}")
        if status == 404:
            return None
        if status != 200:
            self._fail(status, data)
        return data

    def delete_named(self, key):
        status, data = self._call("DELETE", f"/v1/named?key={quote(key, safe='')}")
        if status not in (200, 404):
            self._fail(status, data)


# ================================================================== factory
def cloud_store_from_settings(settings) -> CloudStore:
    mode = settings.get("cloud_mode", "off")
    if mode == "embedded":
        root = settings.get("cloud_embedded_root", "")
        url = f"http://127.0.0.1:{int(settings.get('cloud_embedded_port', 8765))}"
        return CloudStore(url, settings.get("cloud_embedded_token", ""), store_id=f"minicloud:{root}",
                          label="Mini Cloud", local_root=root)
    if mode == "remote":
        url = (settings.get("cloud_url") or "").strip()
        if not url:
            raise StoreError("Enter the Mini Cloud address in Settings first.")
        return CloudStore(url, settings.get("cloud_token", ""))
    raise StoreError("Mini Cloud is turned off. Turn it on in Settings.")


def build_stores(settings, destination):
    """destination: 'local' | 'cloud' | 'both'."""
    stores = []
    if destination in ("local", "both"):
        path = (settings.get("local_path") or "").strip()
        if not path:
            raise StoreError("Choose a local storage folder in Settings first.")
        stores.append(LocalStore(Path(path) / "SafeFile"))
    if destination in ("cloud", "both"):
        stores.append(cloud_store_from_settings(settings))
    return stores


def store_from_id(store_id, settings):
    """Rebuild the store a snapshot was saved to (so old versions stay reachable)."""
    if store_id.startswith("local:"):
        return LocalStore(Path(store_id[6:]), store_id)
    if store_id.startswith("minicloud:"):
        root = store_id[len("minicloud:"):]
        if settings.get("cloud_mode") == "embedded" and settings.get("cloud_embedded_root") == root:
            return cloud_store_from_settings(settings)
        raise StoreError(f"The built-in Mini Cloud folder {root} is not the one currently in use.")
    if store_id.startswith("cloud:"):
        url = store_id[len("cloud:"):]
        if settings.get("cloud_mode") == "remote" and (settings.get("cloud_url") or "").rstrip("/") == url:
            return cloud_store_from_settings(settings)
        raise StoreError(f"The Mini Cloud at {url} is not the one currently configured.")
    raise StoreError(f"Unknown destination: {store_id}")


def validate_destination(project_path, store):
    """Refuse destinations inside the protected folder (or containing it)."""
    root = getattr(store, "local_root", None)
    if not root:
        return
    def norm(p):
        return os.path.normcase(os.path.abspath(os.path.realpath(p)))
    a, b = norm(project_path), norm(root)
    try:
        common = os.path.commonpath([a, b])
    except ValueError:
        return  # different drives
    if common == a:
        raise StoreError("The backup folder is inside the folder being protected. Choose a location outside it.")
    if common == b:
        raise StoreError("The folder being protected is inside the backup folder. Choose a different location.")
