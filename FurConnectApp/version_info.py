"""Resolve FurConnect build/version metadata for local dev and Docker."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

VERSION_FILE = "furconnect_version"


def _format_date(date_raw: str) -> str | None:
    date_raw = date_raw.strip()
    if len(date_raw) == 8 and date_raw.isdigit():
        return f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
    return None


def _format_version(hash_value: str, date_value: str, package_version: str) -> str:
    formatted_date = _format_date(date_value)
    if hash_value and formatted_date:
        return f"Version: {hash_value[:6].upper()} ({formatted_date})"
    return f"Version: {package_version}"


def _read_version_file(base_dir: Path) -> tuple[str | None, str | None]:
    path = base_dir / VERSION_FILE
    if not path.is_file():
        return None, None
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(lines) < 2:
        return None, None
    return lines[0][:6].upper(), lines[1]


def _git_env(base_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = str(base_dir)
    return env


def _read_git(base_dir: Path) -> tuple[str | None, str | None]:
    if not (base_dir / ".git").exists():
        return None, None
    env = _git_env(base_dir)
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=base_dir,
            stderr=subprocess.DEVNULL,
            env=env,
        ).decode("utf-8").strip()[:6].upper()
        git_date = subprocess.check_output(
            ["git", "show", "-s", "--format=%cd", "--date=format:%Y%m%d", "HEAD"],
            cwd=base_dir,
            stderr=subprocess.DEVNULL,
            env=env,
        ).decode("utf-8").strip()
        return git_hash, git_date
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None, None


def write_version_file(base_dir: Path | str) -> bool:
    """Persist git hash/date for runtime when git is unavailable (e.g. Docker)."""
    base_dir = Path(base_dir)
    git_hash, git_date = _read_git(base_dir)
    if not (git_hash and git_date):
        return False
    (base_dir / VERSION_FILE).write_text(f"{git_hash}\n{git_date}\n", encoding="utf-8")
    return True


def resolve_version_string(base_dir: Path | str, package_version: str = "dev") -> str:
    git_hash = os.environ.get("FURCONNECT_GIT_HASH", "").strip()[:6].upper() or None
    git_date = os.environ.get("FURCONNECT_GIT_DATE", "").strip() or None

    if not (git_hash and git_date):
        file_hash, file_date = _read_version_file(Path(base_dir))
        git_hash = git_hash or file_hash
        git_date = git_date or file_date

    if not (git_hash and git_date):
        discovered_hash, discovered_date = _read_git(Path(base_dir))
        git_hash = git_hash or discovered_hash
        git_date = git_date or discovered_date

    return _format_version(git_hash or "", git_date or "", package_version)
