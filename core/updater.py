import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List

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


def _fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    if requests:
        resp = requests.get(url, timeout=10, headers=headers or {})
        resp.raise_for_status()
        return resp.json()
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as resp:
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


def _pick_release(releases: List[Dict[str, Any]], include_prerelease: bool) -> Optional[Dict[str, Any]]:
    for rel in releases:
        if rel.get("draft"):
            continue
        if rel.get("prerelease") and not include_prerelease:
            continue
        return rel
    return None


def _normalize_version(tag: str) -> str:
    if not tag:
        return ""
    return tag.lstrip("vV").strip()


def _resolve_asset(release: Dict[str, Any], asset_name: str) -> Optional[Dict[str, Any]]:
    assets = release.get("assets") or []
    if asset_name:
        for asset in assets:
            if asset.get("name") == asset_name:
                return asset
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith(".zip") or name.endswith(".exe"):
            return asset
    return None


def check_for_update(repo: str, asset_name: str, current_version: str, include_prerelease: bool = False) -> Dict[str, Any]:
    """
    Check GitHub releases and compare versions.
    Returns dict with keys: status, latest_version, manifest, error (optional).
    status: no_update | update_available | error
    """
    if not repo:
        return {"status": "error", "error": "GitHub repo not configured"}
    try:
        headers = {"Accept": "application/vnd.github+json"}
        if include_prerelease:
            url = f"https://api.github.com/repos/{repo}/releases"
            releases = _fetch_json(url, headers=headers)
            release = _pick_release(releases, include_prerelease=True)
        else:
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            release = _fetch_json(url, headers=headers)
        if not release:
            return {"status": "error", "error": "No release found"}
        tag = release.get("tag_name") or release.get("name") or ""
        latest = _normalize_version(tag)
        if not latest:
            return {"status": "error", "error": "Release missing version tag"}
        asset = _resolve_asset(release, asset_name)
        if not asset:
            return {"status": "error", "error": f"Asset not found: {asset_name or '(.zip/.exe)'}"}
        manifest = {
            "version": latest,
            "url": asset.get("browser_download_url"),
            "notes": release.get("body") or "A newer version is available.",
        }
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


def _find_update_root(extract_dir: str, exe_name: str) -> Optional[str]:
    if os.path.isfile(os.path.join(extract_dir, exe_name)):
        return extract_dir
    entries = [p for p in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, p))]
    if len(entries) == 1:
        candidate = os.path.join(extract_dir, entries[0])
        if os.path.isfile(os.path.join(candidate, exe_name)):
            return candidate
        if os.path.isdir(os.path.join(candidate, "_internal")):
            return candidate
    return None


def install_update(download_path: str, relaunch: bool = True) -> Dict[str, Any]:
    """
    Replace the current executable with the downloaded one (Windows).
    If the download is a .zip, attempts to extract the first .exe in it.
    """
    if not download_path or not os.path.exists(download_path):
        return {"status": "error", "error": "Downloaded file not found"}

    if not getattr(sys, "frozen", False):
        return {"status": "error", "error": "Install only supported from bundled EXE"}

    target_exe = sys.executable
    src_path = download_path

    if download_path.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(download_path, "r") as zf:
                extract_dir = tempfile.mkdtemp(prefix="update_extract_")
                zf.extractall(extract_dir)
            exe_name = os.path.basename(target_exe)
            update_root = _find_update_root(extract_dir, exe_name)
            if not update_root:
                return {"status": "error", "error": "Update zip missing expected layout or exe"}
            src_path = update_root
        except Exception as e:
            return {"status": "error", "error": f"Zip extract failed: {e}"}

    bat_path = os.path.join(tempfile.gettempdir(), "atomx_update.bat")
    app_dir = os.path.dirname(target_exe)
    if os.path.isdir(src_path):
        src_dir = src_path
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(
                "@echo off\n"
                "setlocal\n"
                "ping 127.0.0.1 -n 3 >nul\n"
                f"xcopy /E /Y /I \"{src_dir}\\*\" \"{app_dir}\\\" >nul\n"
                + (f"start \"\" \"{target_exe}\"\n" if relaunch else "")
                + "del \"%~f0\"\n"
            )
    else:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(
                "@echo off\n"
                "setlocal\n"
                "ping 127.0.0.1 -n 3 >nul\n"
                f"copy /Y \"{src_path}\" \"{target_exe}\" >nul\n"
                "if errorlevel 1 exit /b 1\n"
                + (f"start \"\" \"{target_exe}\"\n" if relaunch else "")
                + "del \"%~f0\"\n"
            )
    try:
        subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
    except Exception as e:
        return {"status": "error", "error": f"Failed to launch updater: {e}"}
    return {"status": "started", "path": target_exe}
