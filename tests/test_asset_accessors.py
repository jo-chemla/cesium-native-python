"""CachingAssetAccessor with a caller-owned cache, and the Linux CA bundle
default of CurlAssetAccessor."""
import os
import sys

import pytest
from cesium.async_ import CachingAssetAccessor, SqliteCache
from cesium.curl import CurlAssetAccessor, CurlAssetAccessorOptions


def test_caching_accessor_accepts_an_existing_cache(tmp_path):
    cache = SqliteCache(str(tmp_path / "cache.sqlite"), 10)
    inner = CurlAssetAccessor()
    accessor = CachingAssetAccessor(inner, cache)
    assert isinstance(accessor, CachingAssetAccessor)
    # the same cache can back a second accessor
    CachingAssetAccessor(inner, cache, requests_per_cache_prune=5)


def test_caching_accessor_still_accepts_a_path(tmp_path):
    accessor = CachingAssetAccessor(CurlAssetAccessor(), str(tmp_path / "c.sqlite"))
    assert isinstance(accessor, CachingAssetAccessor)


def test_explicit_certificate_file_is_kept():
    options = CurlAssetAccessorOptions()
    options.certificate_file = "/nonexistent/bundle.pem"
    accessor = CurlAssetAccessor(options)
    assert accessor.options.certificate_file == "/nonexistent/bundle.pem"


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only default")
def test_linux_default_certificate_file(monkeypatch):
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    known = [
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/ssl/ca-bundle.pem",
        "/etc/ssl/cert.pem",
    ]
    existing = [p for p in known if os.path.isfile(p)]
    accessor = CurlAssetAccessor()
    if existing:
        assert accessor.options.certificate_file == existing[0]
    else:
        assert accessor.options.certificate_file == ""


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only default")
def test_linux_env_bundle_wins(monkeypatch, tmp_path):
    bundle = tmp_path / "my.pem"
    bundle.write_text("")
    monkeypatch.setenv("CURL_CA_BUNDLE", str(bundle))
    assert CurlAssetAccessor().options.certificate_file == str(bundle)


@pytest.mark.skipif(sys.platform == "linux", reason="other platforms keep curl's default")
def test_non_linux_leaves_certificate_file_empty():
    assert CurlAssetAccessor().options.certificate_file == ""
