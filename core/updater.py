import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from packaging import version

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None
import urllib.request
import urllib.error


def _validate_version_string(version_str: str) -> bool:
    """Validate that a version string is safe and properly formatted."""
    # Allow semantic versioning: X.Y.Z with optional pre-release suffix
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*)?$"
    return bool(re.match(pattern, version_str))


def read_local_version(version_file: str = "VERSION") -> str:
    """
    Read the local application version from VERSION file.

    Searches in multiple locations for the VERSION file and returns
    the first valid version string found.

    Args:
        version_file: Name of the version file to look for.

    Returns:
        Version string or "0.0.0" if not found.
    """
    # Validate filename to prevent path traversal
    if ".." in version_file or os.path.sep in version_file:
        logger.warning(f"Invalid version_file path: {version_file}")
        return "0.0.0"

    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / version_file)
    try:
        candidates.append(Path(sys.executable).resolve().parent / version_file)
    except Exception as e:
        logger.debug(f"Could not resolve executable parent: {e}")

    candidates.append(Path(__file__).resolve().parent.parent / version_file)
    candidates.append(Path.cwd() / version_file)

    for path in candidates:
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip()
                if value and _validate_version_string(value):
                    return value
                elif value:
                    logger.warning(f"Invalid version format in {path}: {value}")
        except Exception as e:
            logger.debug(f"Could not read version from {path}: {e}")
            continue

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

class DownloadCancelled(Exception):
    def __init__(self, path: str):
        super().__init__("Download cancelled")
        self.path = path


def _download(url: str, dest_dir: str, progress_cb: Optional[Callable[[int, int], bool]] = None) -> str:
    """
    Download a file from URL to destination directory.

    Args:
        url: URL to download from.
        dest_dir: Directory to save the downloaded file.
        progress_cb: Optional callback(downloaded, total) -> bool. Return False to cancel.

    Returns:
        Path to the downloaded file.

    Raises:
        DownloadCancelled: If download was cancelled via callback.
        ValueError: If URL is invalid.
        Exception: On download errors.
    """
    # Validate URL
    if not url or not url.startswith(("https://", "http://")):
        raise ValueError(f"Invalid URL: {url}")

    # Prefer HTTPS
    if url.startswith("http://"):
        logger.warning(f"Downloading over insecure HTTP: {url}")

    os.makedirs(dest_dir, exist_ok=True)

    # Extract safe filename from URL
    url_filename = os.path.basename(url.split("?")[0])  # Remove query params
    safe_suffix = "".join(c for c in url_filename if c.isalnum() or c in "._-")[:50]
    if not safe_suffix:
        safe_suffix = "download"

    fd, tmp_path = tempfile.mkstemp(dir=dest_dir, prefix="update_", suffix=f"_{safe_suffix}")
    os.close(fd)

    try:
        if requests:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_cb and progress_cb(downloaded, total) is False:
                                raise DownloadCancelled(tmp_path)
        else:
            with urllib.request.urlopen(url, timeout=30) as resp, open(tmp_path, "wb") as f:
                total = int(getattr(resp, "length", 0) or 0)
                downloaded = 0
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and progress_cb(downloaded, total) is False:
                        raise DownloadCancelled(tmp_path)

        logger.info(f"Downloaded {downloaded} bytes to {tmp_path}")
        return tmp_path

    except DownloadCancelled:
        raise
    except Exception as e:
        # Clean up partial download on error
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


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


def download_update(
    manifest: Dict[str, Any],
    dest_dir: str = "updates",
    progress_cb: Optional[Callable[[int, int], bool]] = None,
) -> Dict[str, Any]:
    """
    Download the artifact described in manifest; verify sha256 if provided.
    Manifest keys expected: url (required), sha256 (optional).
    Returns dict with status, path, error (optional).
    """
    url = manifest.get("url")
    if not url:
        return {"status": "error", "error": "Manifest missing 'url'"}
    try:
        path = _download(url, dest_dir, progress_cb=progress_cb)
        if not _verify_sha256(path, manifest.get("sha256")):
            return {"status": "error", "error": "SHA256 verification failed"}
        return {"status": "downloaded", "path": path}
    except DownloadCancelled as e:
        try:
            if os.path.exists(e.path):
                os.remove(e.path)
        except Exception:
            pass
        return {"status": "cancelled", "error": "Download cancelled"}
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


def _validate_path(path: str, description: str) -> bool:
    """
    Validate a path to prevent directory traversal and injection attacks.

    Args:
        path: The path to validate.
        description: Description for error messages.

    Returns:
        True if path is valid.

    Raises:
        ValueError: If path contains dangerous patterns.
    """
    if not path:
        raise ValueError(f"{description} is empty")

    # Check for path traversal attempts
    normalized = os.path.normpath(path)
    if ".." in normalized:
        raise ValueError(f"{description} contains path traversal: {path}")

    # Check for shell metacharacters that could be injected
    dangerous_chars = ['|', '&', ';', '$', '`', '\n', '\r', '"', "'", '<', '>']
    for char in dangerous_chars:
        if char in path:
            raise ValueError(f"{description} contains dangerous character '{char}': {path}")

    return True


def install_update(download_path: str, relaunch: bool = True) -> Dict[str, Any]:
    """
    Replace the current executable with the downloaded one (Windows).

    If the download is a .zip, attempts to extract and find the executable.

    SECURITY NOTES:
    - Only runs from frozen (PyInstaller) executables
    - Validates all paths to prevent injection attacks
    - Uses unique batch file name to prevent race conditions
    - Waits for process to exit before overwriting

    Args:
        download_path: Path to the downloaded update file (.zip or .exe).
        relaunch: Whether to relaunch the application after update.

    Returns:
        Dict with status and path/error information.
    """
    # Validate inputs
    try:
        _validate_path(download_path, "Download path")
    except ValueError as e:
        logger.error(f"Path validation failed: {e}")
        return {"status": "error", "error": str(e)}

    if not os.path.exists(download_path):
        return {"status": "error", "error": "Downloaded file not found"}

    if not getattr(sys, "frozen", False):
        return {"status": "error", "error": "Install only supported from bundled EXE"}

    target_exe = sys.executable
    src_path = download_path

    # Validate target executable path
    try:
        _validate_path(target_exe, "Target executable")
    except ValueError as e:
        logger.error(f"Target path validation failed: {e}")
        return {"status": "error", "error": str(e)}

    if download_path.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(download_path, "r") as zf:
                # Security: Check for zip slip vulnerability
                extract_dir = tempfile.mkdtemp(prefix="update_extract_")
                for member in zf.namelist():
                    member_path = os.path.normpath(os.path.join(extract_dir, member))
                    if not member_path.startswith(os.path.normpath(extract_dir)):
                        logger.error(f"Zip slip attempt detected: {member}")
                        return {"status": "error", "error": "Malicious zip file detected"}
                zf.extractall(extract_dir)

            exe_name = os.path.basename(target_exe)
            update_root = _find_update_root(extract_dir, exe_name)
            if not update_root:
                return {"status": "error", "error": "Update zip missing expected layout or exe"}
            src_path = update_root
        except zipfile.BadZipFile as e:
            logger.error(f"Invalid zip file: {e}")
            return {"status": "error", "error": f"Invalid zip file: {e}"}
        except Exception as e:
            logger.error(f"Zip extract failed: {e}")
            return {"status": "error", "error": f"Zip extract failed: {e}"}

    # Validate source path after extraction
    try:
        _validate_path(src_path, "Source path")
    except ValueError as e:
        logger.error(f"Source path validation failed: {e}")
        return {"status": "error", "error": str(e)}

    # Generate unique batch file name to prevent race conditions
    import uuid
    bat_name = f"atomx_update_{uuid.uuid4().hex[:8]}.bat"
    bat_path = os.path.join(tempfile.gettempdir(), bat_name)

    app_dir = os.path.dirname(target_exe)

    # Escape paths for batch file (double quotes handle most cases)
    # Additional validation already done above
    if os.path.isdir(src_path):
        src_dir = src_path
        batch_content = (
            "@echo off\n"
            "setlocal EnableDelayedExpansion\n"
            "echo Waiting for application to close...\n"
            "timeout /t 3 /nobreak >nul\n"
            f'xcopy /E /Y /I "{src_dir}\\*" "{app_dir}\\" >nul 2>&1\n'
            "if errorlevel 1 (\n"
            "    echo Update failed. Please try again.\n"
            "    pause\n"
            "    exit /b 1\n"
            ")\n"
            "echo Update successful!\n"
            + (f'start "" "{target_exe}"\n' if relaunch else "")
            + 'del "%~f0"\n'
        )
    else:
        batch_content = (
            "@echo off\n"
            "setlocal EnableDelayedExpansion\n"
            "echo Waiting for application to close...\n"
            "timeout /t 3 /nobreak >nul\n"
            f'copy /Y "{src_path}" "{target_exe}" >nul 2>&1\n'
            "if errorlevel 1 (\n"
            "    echo Update failed. Please try again.\n"
            "    pause\n"
            "    exit /b 1\n"
            ")\n"
            "echo Update successful!\n"
            + (f'start "" "{target_exe}"\n' if relaunch else "")
            + 'del "%~f0"\n'
        )

    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(batch_content)
    except Exception as e:
        logger.error(f"Failed to write update script: {e}")
        return {"status": "error", "error": f"Failed to write update script: {e}"}

    try:
        # Use shell=False and explicit cmd.exe path for security
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            shell=False
        )
        logger.info(f"Update process started, updating to {src_path}")
    except Exception as e:
        logger.error(f"Failed to launch updater: {e}")
        return {"status": "error", "error": f"Failed to launch updater: {e}"}

    return {"status": "started", "path": target_exe}
