"""OIDC test fixtures — ROPC token exchange and Selenium WebDriver."""

import os
import time

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


# ─── Environment defaults (match dev environment) ─────────────────

GASKET_URL = os.environ.get("GASKET_URL", "https://portal.gasket-dev.local")
OIDC_TOKEN_URL = os.environ.get(
    "OIDC_TOKEN_URL",
    "https://authentik.gasket-dev.local/application/o/token/",
)
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "gg-client-id")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "gg-client-secret")


# ─── Health check ─────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def wait_for_gasket():
    """Wait for Gasket to be healthy before running any OIDC tests."""
    url = f"{GASKET_URL}/health"
    timeout = 60
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


# ─── ROPC token helper ────────────────────────────────────────────


def fetch_ropc_token(username, password):
    """Exchange username + password for tokens via Authentik's ROPC-style grant.

    Authentik handles ROPC via grant_type=client_credentials with
    username/password passed in the request body.
    """
    response = requests.post(
        OIDC_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": OIDC_CLIENT_ID,
            "client_secret": OIDC_CLIENT_SECRET,
            "username": username,
            "password": password,
            "scope": "openid email profile entitlements",
        },
        verify=False,  # Dev environment uses self-signed certs
    )
    return response


# ─── Pytest fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="session")
def gasket_url():
    """Base URL for the Gasket portal."""
    return GASKET_URL


@pytest.fixture(scope="session")
def oidc_token_url():
    """OIDC token endpoint URL."""
    return OIDC_TOKEN_URL


@pytest.fixture(scope="session")
def browser():
    """Headless Chromium browser for Selenium tests."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    yield driver
    driver.quit()


@pytest.fixture
def user2_token():
    """ROPC token for user2 (gasket-users member).

    Uses the app password token created by provision.sh.
    """
    resp = fetch_ropc_token("user2", "user2-app-password")
    assert resp.status_code == 200, f"ROPC failed for user2: {resp.text}"
    return resp.json()


@pytest.fixture
def user3_token():
    """ROPC token for user3 (gasket-users + gasket-admins member).

    Uses the app password token created by provision.sh.
    """
    resp = fetch_ropc_token("user3", "user3-app-password")
    assert resp.status_code == 200, f"ROPC failed for user3: {resp.text}"
    return resp.json()


# ─── Screenshot on failure ────────────────────────────────────────

RESULTS_DIR = os.environ.get("TEST_RESULTS_DIR", "/results")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a browser screenshot when a Selenium test fails."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        # Try to grab the browser fixture
        driver = item.funcargs.get("browser")
        if driver:
            os.makedirs(RESULTS_DIR, exist_ok=True)
            screenshot_path = os.path.join(
                RESULTS_DIR, f"{item.name}.png"
            )
            driver.save_screenshot(screenshot_path)
