"""Top-level test fixtures — general tests run against the Gasket test environment."""

import os
import time

import pytest
import requests


GASKET_URL = os.environ.get("GASKET_URL", "http://localhost:5000")


class GasketClient:
    """Simple HTTP client for testing against the running Gasket instance."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = False  # Dev certs are self-signed

    def get(self, path, **kwargs):
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path, **kwargs):
        return self.session.post(f"{self.base_url}{path}", **kwargs)

    def put(self, path, **kwargs):
        return self.session.put(f"{self.base_url}{path}", **kwargs)

    def delete(self, path, **kwargs):
        return self.session.delete(f"{self.base_url}{path}", **kwargs)


@pytest.fixture(scope="session", autouse=True)
def wait_for_gasket():
    """Wait for Gasket to be healthy before running any tests."""
    url = f"{GASKET_URL}/health"
    timeout = 30
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=3, verify=False)
            if resp.status_code == 200:
                return
        except requests.ConnectionError:
            pass
        time.sleep(2)
    pytest.fail(f"Gasket not ready at {url} after {timeout}s")


@pytest.fixture(scope="session")
def client():
    """HTTP client pointed at the running Gasket instance."""
    return GasketClient(GASKET_URL)


@pytest.fixture(scope="session")
def gasket_url():
    """Base URL for the Gasket instance."""
    return GASKET_URL
