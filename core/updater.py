import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from packaging import version

try:
    import requests
except Exception:  # pragma: no cover
    requests = None
import urllib.request
import urllib.error


def read_local_version(version_file: str = "VERSION") -> str:
    try:
        return Path(version_file).read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def _fetch_manifest(manifest_url: str) -> Dict[str, Any]:
    if not manifest_url:
        raise ValueError("Manifest URL not configured")
    if requests:
        resp = requests.get(manifest_url, timeout=6)
        resp.raise_for_status()
        return resp.json()
    with urllib.request.urlopen(manifest_url, timeout=6) as resp:
        data = resp.read().decode("utf-8")
        return json.loads(data)


def _verify_sha256(path: str, expected: Optional[str]) -> bool:
    if not expected:
        return True
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected.lower()


def _download(url: str, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dest_dir, prefix="update_", suffix=os.path.basename(url))
    os.close(fd)
    if requests:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
    else:
        with urllib.request.urlopen(url, timeout=30) as resp, open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
    return tmp_path


def check_for_update(manifest_url: str, current_version: str) -> Dict[str, Any]:
    """
    Fetch manifest and compare versions.
    Returns dict with keys: status, latest_version, manifest, error (optional).
    status: no_update | update_available | error
    """
    try:
        manifest = _fetch_manifest(manifest_url)
        latest = manifest.get("version")
        if not latest:
            return {"status": "error", "error": "Manifest missing 'version'"}
        if version.parse(latest) > version.parse(current_version):
            return {"status": "update_available", "latest_version": latest, "manifest": manifest}
        return {"status": "no_update", "latest_version": latest, "manifest": manifest}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def download_update(manifest: Dict[str, Any], dest_dir: str = "updates") -> Dict[str, Any]:
    """
    Download the artifact described in manifest; verify sha256 if provided.
    Manifest keys expected: url (required), sha256 (optional).
    Returns dict with status, path, error (optional).
    """
    url = manifest.get("url")
    if not url:
        return {"status": "error", "error": "Manifest missing 'url'"}
    try:
        path = _download(url, dest_dir)
        if not _verify_sha256(path, manifest.get("sha256")):
            return {"status": "error", "error": "SHA256 verification failed"}
        return {"status": "downloaded", "path": path}
    except Exception as e:
        return {"status": "error", "error": str(e)}
