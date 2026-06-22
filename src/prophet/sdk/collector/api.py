"""Collector API: fetch the prophet-node binary (so the whole factory flow is SDK-driven)."""

from __future__ import annotations

import re
import tarfile
import tempfile
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

    Example:
        # Fetch + unpack the latest stable ARM7 binary, ready to flash
        binary = prophet.collector.download(arch="arm7", extract=True, dest="./dist")
        # binary -> ./dist/prophet (executable)

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
    ) -> Path:
        """
        Download the collector binary for a platform.

        Args:
            dest: file path for the tarball, or (with extract=True) the directory to
                  unpack into. Defaults to the release filename / current directory.
            os/arch: target platform (e.g. os="linux", arch="arm7").
            channel: "stable" (default) or "dev".
            extract: if True, unpack the .tar.gz and return the path to the
                     executable `prophet` binary (chmod +x applied).

        Returns:
            Path to the downloaded tarball, or to the extracted binary if extract=True.
        """
        url = self.download_url(os=os, arch=arch, channel=channel)
        resp = self._client._session.get(
            url, stream=True, timeout=self._client._timeout, allow_redirects=True
        )
        raise_for_response(resp)

        filename = _filename_from_response(resp) or f"prophet_collector_{os}_{arch}.tar.gz"

        if extract:
            return self._download_and_extract(resp, dest, filename)

        tarball = Path(dest) if dest else Path(filename)
        _stream_to_file(resp, tarball)
        return tarball

    def _download_and_extract(
        self, resp: requests.Response, dest: str | Path | None, filename: str
    ) -> Path:
        out_dir = Path(dest) if dest else Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)
        binary = out_dir / _BINARY_NAME

        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / filename
            _stream_to_file(resp, tarball)
            with tarfile.open(tarball, "r:gz") as tar:
                member = next(
                    (m for m in tar.getmembers() if Path(m.name).name == _BINARY_NAME), None
                )
                if member is None:
                    raise APIError(f"'{_BINARY_NAME}' not found in {filename}", status_code=0)
                # Read the member directly (no tar.extract) — avoids path-traversal
                # and the 3.14 extraction-filter deprecation; we control the dest.
                src = tar.extractfile(member)
                if src is None:
                    raise APIError(f"'{_BINARY_NAME}' is not a file in {filename}", status_code=0)
                binary.write_bytes(src.read())

        binary.chmod(0o755)
        return binary


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
