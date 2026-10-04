"""Fetch the DistilBERT weights (255 MB) from the model-v1 GitHub release.

    python -m app.ml.download_model          # from backend/, once per machine

The repo is private, so this uses the GitHub CLI (`gh auth login` once) or a
GITHUB_TOKEN environment variable. The file is checked against its SHA-256, so a
broken download is never loaded. Without it the backend falls back to TF-IDF.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

REPO, TAG, ASSET = "zdencarnoa/HackYeah-", "model-v1", "model.safetensors"
TARGET = Path(__file__).resolve().parent / "models" / "transformer_syn" / ASSET
SHA256 = "5c41499e68a42ce311c48099a241743b14933f886c49b560aa0f8a3fbbefe49a"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_valid(path: Path = TARGET) -> bool:
    return path.exists() and sha256(path) == SHA256


def _with_gh(tmp: Path) -> bool:
    if not shutil.which("gh"):
        return False
    result = subprocess.run(["gh", "release", "download", TAG, "-R", REPO, "-p", ASSET, "-O", str(tmp), "--clobber"])
    return result.returncode == 0


def _with_token(tmp: Path) -> bool:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return False
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    release = httpx.get(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}", headers=headers, timeout=30)
    release.raise_for_status()
    asset = next(a for a in release.json()["assets"] if a["name"] == ASSET)
    with httpx.stream("GET", asset["url"], headers=headers | {"Accept": "application/octet-stream"},
                      follow_redirects=True, timeout=None) as r, tmp.open("wb") as f:
        r.raise_for_status()
        for chunk in r.iter_bytes(1 << 20):
            f.write(chunk)
    return True


def main() -> int:
    if is_valid():
        print(f"already present and verified: {TARGET}")
        return 0
    tmp = TARGET.with_suffix(".part")
    if not (_with_gh(tmp) or _with_token(tmp)):
        print("Could not download: run `gh auth login` (GitHub CLI) or set GITHUB_TOKEN, then retry.")
        return 1
    if not is_valid(tmp):
        tmp.unlink(missing_ok=True)
        print("Download failed the SHA-256 check; nothing was installed.")
        return 1
    tmp.replace(TARGET)
    print(f"installed and verified: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
