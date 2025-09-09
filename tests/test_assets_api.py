import os
import pytest
import requests


ASSETS_ORIGIN = os.getenv("TYPUS_ASSETS_ORIGIN", "https://assets.polli.ai")


def _enabled(var: str) -> bool:
    return os.getenv(var, "0") in {"1", "true", "TRUE"}


@pytest.mark.skipif(not _enabled("TYPUS_NETWORK_TESTS"), reason="network checks disabled by default")
def test_assets_healthz():
    url = f"{ASSETS_ORIGIN}/healthz"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    assert data.get("status") == "ok"


@pytest.mark.skipif(not _enabled("TYPUS_NETWORK_TESTS"), reason="network checks disabled by default")
def test_assets_openapi_available():
    url = f"{ASSETS_ORIGIN}/openapi.json"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    assert r.headers.get("content-type", "").startswith("application/json")

