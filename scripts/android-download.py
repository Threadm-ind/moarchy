#!/usr/bin/env python3
"""Download and safely unpack the pinned Android bundle without installing it."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request


ARTIFACT_NAME = "moarchy-android-474130c2f0b4.tar.gz"
ARCHIVE_ROOT = "moarchy-android"
SETUP_RELATIVE_PATH = Path("moarchy-android/android/setup.sh")
EXPECTED_BYTES = 125_542_257
EXPECTED_SHA256 = "35f97e116111868b2634d14681c0600c9b101e7571cc5d728423e2b4d329bdaa"
MIN_FREE_BYTES = 4 * 1024**3
MAX_MEMBERS = 1_000
MAX_UNPACKED_BYTES = 256 * 1024**2
CHUNK_BYTES = 1024 * 1024


class DownloadError(RuntimeError):
    """The archive was unavailable, did not match its pin, or was unsafe."""


@dataclass(frozen=True)
class DownloadResult:
    stage: Path
    archive: Path
    extracted: Path


def artifact_url(base_url: str) -> str:
    """Return the exact artifact URL while accepting a conservative HTTPS prefix."""
    parsed = urllib.parse.urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise DownloadError(
            "base URL must be an HTTPS URL without credentials, query, or fragment"
        )
    segments = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if any(part in {".", ".."} for part in segments):
        raise DownloadError("base URL path must not contain traversal segments")
    path = "/" + "/".join([*segments, ARTIFACT_NAME])
    return urllib.parse.urlunsplit(("https", parsed.netloc, path, "", ""))


def require_space(home: Path) -> None:
    stats = os.statvfs(home)
    available = stats.f_bavail * stats.f_frsize
    if available < MIN_FREE_BYTES:
        raise DownloadError(
            f"requires 4 GiB free in Debian home; only {available} bytes available"
        )
    if stats.f_files and stats.f_favail < MAX_MEMBERS + 8:
        raise DownloadError("insufficient free inodes in home for Android download")


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    if len(members) > MAX_MEMBERS:
        raise DownloadError("archive has too many members")
    unpacked = 0
    for member in members:
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts or not member.name:
            raise DownloadError("archive contains unsafe member path")
        if name.parts[0] != ARCHIVE_ROOT:
            raise DownloadError("archive contains an unexpected root")
        if member.isreg():
            unpacked += member.size
            if unpacked >= MAX_UNPACKED_BYTES:
                raise DownloadError("archive unpacks beyond the allowed size")
    return members


def _download(url: str, destination: Path) -> None:
    digest = hashlib.sha256()
    total = 0
    request = urllib.request.Request(
        url, headers={"User-Agent": "moarchy-android-downloader"}
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=20) as response,
            destination.open("wb") as output,
        ):
            while chunk := response.read(CHUNK_BYTES):
                total += len(chunk)
                if total > EXPECTED_BYTES:
                    raise DownloadError("download exceeds pinned byte length")
                digest.update(chunk)
                output.write(chunk)
    except DownloadError:
        raise
    except OSError as error:
        raise DownloadError(f"download failed: {error}") from error
    except Exception as error:
        raise DownloadError(f"download failed: {error}") from error
    if total != EXPECTED_BYTES:
        raise DownloadError("download length does not match pinned artifact")
    if digest.hexdigest() != EXPECTED_SHA256:
        raise DownloadError("download checksum does not match pinned artifact")


def prepare_download(base_url: str, home: Path) -> DownloadResult:
    """Download, verify, and extract below *home*; never invoke an installer."""
    url = artifact_url(base_url)
    require_space(home)
    stage = Path(tempfile.mkdtemp(prefix="moarchy-download-", dir=home))
    archive_path = stage / ARTIFACT_NAME
    extracted = stage / "extracted"
    try:
        _download(url, archive_path)
        with tarfile.open(archive_path, "r:gz") as archive:
            members = safe_members(archive)
            extracted.mkdir()
            archive.extractall(extracted, members=members, filter="data")
        return DownloadResult(stage, archive_path, extracted)
    except Exception as error:
        shutil.rmtree(stage, ignore_errors=True)
        if isinstance(error, DownloadError):
            raise
        if isinstance(error, (tarfile.TarError, OSError)):
            raise DownloadError(f"unsafe or unreadable archive: {error}") from error
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", required=True, help="HTTPS directory holding the pinned bundle"
    )
    args = parser.parse_args()
    try:
        result = prepare_download(args.base_url, Path.home())
    except DownloadError as error:
        parser.error(str(error))
    print("Downloaded and verified; nothing installed")
    print(f"Run setup manually from: {result.extracted / SETUP_RELATIVE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
