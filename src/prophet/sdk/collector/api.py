"""Collector API: fetch the prophet-node binary (so the whole factory flow is SDK-driven)."""

from __future__ import annotations

import os
import re
import shutil
import tarfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import requests

from ..exceptions import APIError, raise_for_response

if TYPE_CHECKING:
    from ..client import Prophet

OS = Literal["linux", "darwin", "windows"]
Arch = Literal["amd64", "arm7", "arm64"]
Channel = Literal["stable", "dev"]

# The binary inside every release tarball.
_BINARY_NAME = "prophet"


class CollectorAPI:
    """
    Download the prophet-node collector binary. Accessed via `prophet.collector`.

    The controller serves the latest signed build per platform/channel (it proxies
    the private release repo), so callers need no GitHub access. This lets a factory
    line pull the binary through the same SDK it uses to provision.

    Downloads are cached on disk keyed by the release's versioned filename, so
    repeated calls (e.g. flashing a batch of the same SKU) don't re-transfer the
    binary — but a new release (new filename) is fetched automatically. Cache dir:
    $PROPHET_SDK_CACHE_DIR, else $XDG_CACHE_HOME/prophet-sdk, else ~/.cache/prophet-sdk.

    Example:
        # Fetch + unpack the latest stable ARM7 binary, ready to flash
        binary = prophet.collector.download(arch="arm7", extract=True, dest="./dist")

        # Or just the URL for a curl-based install step
        url = prophet.collector.download_url(arch="arm7")
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def download_url(
        self, *, os: OS = "linux", arch: Arch = "amd64", channel: Channel = "stable"
    ) -> str:
        """
        The controller URL that 302-redirects to the latest signed binary for a
        platform. Stable + always-latest (resolves the newest release per request),
        so it's safe to bake into an install script.
        """
        return (
            f"{self._client._base_url}/rest/collector/download/1.0"
            f"?os={os}&arch={arch}&channel={channel}"
        )

    def download(
        self,
        dest: str | Path | None = None,
        *,
        os: OS = "linux",
        arch: Arch = "amd64",
        channel: Channel = "stable",
        extract: bool = False,
        cache: bool = True,
    ) -> Path:
        """
        Download the collector binary for a platform (cached on disk by version).

        Args:
            dest: file path for the tarball, or (with extract=True) the directory to
                  unpack into. Defaults to the release filename / current directory.
            os/arch: target platform (e.g. os="linux", arch="arm7").
            channel: "stable" (default) or "dev".
            extract: if True, unpack the .tar.gz and return the path to the
                     executable `prophet` binary (chmod +x applied).
            cache: reuse a cached binary of the same version if present (default True).
                   Set False to force a fresh fetch.

        Returns:
            Path to the downloaded tarball, or to the extracted binary if extract=True.
        """
        tarball = self._fetch_tarball(os=os, arch=arch, channel=channel, cache=cache)

        if extract:
            out_dir = Path(dest) if dest else Path.cwd()
            return _extract_binary(tarball, out_dir)

        target = Path(dest) if dest else Path(tarball.name)
        if target.resolve() != tarball.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tarball, target)
        return target

    def _fetch_tarball(self, *, os: OS, arch: Arch, channel: Channel, cache: bool) -> Path:
        """Return a path to the release tarball, from cache when possible."""
        url = self.download_url(os=os, arch=arch, channel=channel)
        resp = self._client._session.get(
            url, stream=True, timeout=self._client._timeout, allow_redirects=True
        )
        raise_for_response(resp)

        filename = _filename_from_response(resp)
        # Only cache when the server gives a versioned filename — otherwise we
        # can't tell builds apart and could serve a stale binary.
        if not filename:
            tmp = _cache_dir() / f"prophet_collector_{os}_{arch}_{uuid.uuid4().hex}.tar.gz"
            _stream_to_file(resp, tmp)
            return tmp

        cache_file = _cache_dir() / filename
        if cache and cache_file.exists():
            resp.close()  # cache hit — skip the (large) body transfer
            return cache_file

        _stream_to_cache(resp, cache_file)
        return cache_file


def _extract_binary(tarball: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    binary = out_dir / _BINARY_NAME
    with tarfile.open(tarball, "r:gz") as tar:
        member = next((m for m in tar.getmembers() if Path(m.name).name == _BINARY_NAME), None)
        if member is None:
            raise APIError(f"'{_BINARY_NAME}' not found in {tarball.name}", status_code=0)
        # Read the member directly (no tar.extract) — avoids path-traversal and the
        # 3.14 extraction-filter deprecation; we control the dest.
        src = tar.extractfile(member)
        if src is None:
            raise APIError(f"'{_BINARY_NAME}' is not a file in {tarball.name}", status_code=0)
        binary.write_bytes(src.read())
    binary.chmod(0o755)
    return binary


def _cache_dir() -> Path:
    base = (
        os.environ.get("PROPHET_SDK_CACHE_DIR")
        or os.environ.get("XDG_CACHE_HOME")
        or str(Path.home() / ".cache")
    )
    return Path(base) / "prophet-sdk" / "collector"


def _filename_from_response(resp: requests.Response) -> str | None:
    cd = resp.headers.get("content-disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    return match.group(1) if match else None


def _stream_to_file(resp: requests.Response, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)


def _stream_to_cache(resp: requests.Response, cache_file: Path) -> None:
    """Stream to a temp file in the cache dir, then atomically rename into place."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_file.with_name(f".{cache_file.name}.{uuid.uuid4().hex}.tmp")
    try:
        _stream_to_file(resp, tmp)
        os.replace(tmp, cache_file)
    finally:
        tmp.unlink(missing_ok=True)
