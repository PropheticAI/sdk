"""Tests for the collector binary-download API."""

from __future__ import annotations

import io
import os
import stat
import tarfile

import pytest
import responses

from prophet.sdk import ValidationError
from tests.conftest import BASE_URL

DOWNLOAD_URL = f"{BASE_URL}/rest/collector/download/1.0"
DISPOSITION = "attachment; filename=prophet_collector_v0.3.0_linux_arm7.tar.gz"


def _make_tarball(binary: bytes) -> bytes:
    """Build a .tar.gz containing a single `prophet` member."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="prophet")
        info.size = len(binary)
        tar.addfile(info, io.BytesIO(binary))
    return buf.getvalue()


def test_download_url(prophet):
    assert prophet.collector.download_url(os="linux", arch="arm7") == (
        f"{BASE_URL}/rest/collector/download/1.0?os=linux&arch=arm7&channel=stable"
    )
    assert "channel=dev" in prophet.collector.download_url(arch="amd64", channel="dev")


@responses.activate
def test_download_tarball_to_dest(prophet, tmp_path):
    body = _make_tarball(b"binary-contents")
    responses.add(
        responses.GET, DOWNLOAD_URL, body=body, status=200,
        content_type="application/octet-stream",
        headers={"content-disposition": DISPOSITION},
    )
    dest = tmp_path / "collector.tar.gz"
    path = prophet.collector.download(dest=str(dest), arch="arm7")
    assert path == dest
    assert dest.read_bytes() == body


@responses.activate
def test_download_extracts_executable_binary(prophet, tmp_path):
    binary = b"\x7fELF...prophet-collector"
    responses.add(
        responses.GET, DOWNLOAD_URL, body=_make_tarball(binary), status=200,
        headers={"content-disposition": DISPOSITION},
    )
    path = prophet.collector.download(arch="arm7", extract=True, dest=str(tmp_path))
    assert path == tmp_path / "prophet"
    assert path.read_bytes() == binary
    assert os.stat(path).st_mode & stat.S_IXUSR  # chmod +x applied


@responses.activate
def test_second_download_served_from_cache(prophet, tmp_path):
    # Two responses with the SAME versioned filename but different bodies. The
    # second call must serve the cached (first) binary, proving no re-download.
    responses.add(responses.GET, DOWNLOAD_URL, body=_make_tarball(b"AAAA"), status=200,
                  headers={"content-disposition": DISPOSITION})
    responses.add(responses.GET, DOWNLOAD_URL, body=_make_tarball(b"BBBB"), status=200,
                  headers={"content-disposition": DISPOSITION})
    first = prophet.collector.download(arch="arm7", extract=True, dest=str(tmp_path / "a"))
    second = prophet.collector.download(arch="arm7", extract=True, dest=str(tmp_path / "b"))
    assert first.read_bytes() == b"AAAA"
    assert second.read_bytes() == b"AAAA"  # cache hit, NOT the second response's body


@responses.activate
def test_cache_false_forces_refetch(prophet, tmp_path):
    responses.add(responses.GET, DOWNLOAD_URL, body=_make_tarball(b"AAAA"), status=200,
                  headers={"content-disposition": DISPOSITION})
    responses.add(responses.GET, DOWNLOAD_URL, body=_make_tarball(b"BBBB"), status=200,
                  headers={"content-disposition": DISPOSITION})
    prophet.collector.download(arch="arm7", extract=True, dest=str(tmp_path / "a"))
    refetched = prophet.collector.download(
        arch="arm7", extract=True, dest=str(tmp_path / "b"), cache=False
    )
    assert refetched.read_bytes() == b"BBBB"  # cache bypassed


@responses.activate
def test_new_version_invalidates_cache(prophet, tmp_path):
    responses.add(responses.GET, DOWNLOAD_URL, body=_make_tarball(b"V1"), status=200,
                  headers={"content-disposition": "attachment; filename=prophet_v1_arm7.tar.gz"})
    responses.add(responses.GET, DOWNLOAD_URL, body=_make_tarball(b"V2"), status=200,
                  headers={"content-disposition": "attachment; filename=prophet_v2_arm7.tar.gz"})
    v1 = prophet.collector.download(arch="arm7", extract=True, dest=str(tmp_path / "a"))
    v2 = prophet.collector.download(arch="arm7", extract=True, dest=str(tmp_path / "b"))
    assert v1.read_bytes() == b"V1"
    assert v2.read_bytes() == b"V2"  # different filename -> cache miss -> fresh fetch


@responses.activate
def test_download_unsupported_platform_raises(prophet, tmp_path):
    responses.add(
        responses.GET, DOWNLOAD_URL,
        json={"error": "Unsupported platform: windows/arm7"}, status=400,
    )
    with pytest.raises(ValidationError):
        prophet.collector.download(dest=str(tmp_path / "x"), os="windows", arch="arm7")
