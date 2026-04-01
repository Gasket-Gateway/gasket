"""OIDC test fixtures — ROPC token exchange, Selenium WebDriver, and authenticated sessions."""

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


# ─── Shadow DOM helpers ───────────────────────────────────────────

# Authentik renders its login form inside nested Shadow DOM web components.
# Standard Selenium selectors can't pierce shadow roots, so we use JS.

JS_FIND_UID_INPUT = """(function() {
    var executor = document.querySelector('ak-flow-executor');
    if (!executor || !executor.shadowRoot) return null;
    var stage = executor.shadowRoot.querySelector(
        'ak-stage-identification, ak-stage-password, ak-stage-autosubmit'
    );
    if (!stage || !stage.shadowRoot) return null;
    return stage.shadowRoot.querySelector('input[name="uidField"]');
})()"""

JS_FIND_PW_INPUT = """(function() {
    var executor = document.querySelector('ak-flow-executor');
    if (!executor || !executor.shadowRoot) return null;
    var stage = executor.shadowRoot.querySelector(
        'ak-stage-password, ak-stage-identification'
    );
    if (!stage || !stage.shadowRoot) return null;
    return stage.shadowRoot.querySelector('input[name="password"]');
})()"""

JS_FIND_SUBMIT = """(function() {
    var executor = document.querySelector('ak-flow-executor');
    if (!executor || !executor.shadowRoot) return null;
    var stage = executor.shadowRoot.querySelector(
        'ak-stage-identification, ak-stage-password, ak-stage-consent, ak-stage-autosubmit'
    );
    if (!stage || !stage.shadowRoot) return null;
    return stage.shadowRoot.querySelector('button[type="submit"]');
})()"""


def _wait_for_js(browser, js_script, timeout=15):
    """Poll until a JS script returns a non-null element."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        el = browser.execute_script(f"return {js_script}")
        if el:
            return el
        time.sleep(0.5)
    return None


def authentik_login(browser, gasket_url, username, password):
    """Perform a full Authentik browser login flow, piercing Shadow DOM.

    Clears cookies first, navigates to /auth/login, completes the Authentik
    username + password stages, and waits for the redirect back to Gasket.
    """
    # Clear cookies on the current domain (Gasket)
    browser.delete_all_cookies()

    # Also clear Authentik's SSO cookies — delete_all_cookies() only affects
    # the current domain, so we must navigate to Authentik first.  Without
    # this, the previous user's SSO session persists and Authentik silently
    # auto-authenticates as the wrong user.
    authentik_base = OIDC_TOKEN_URL.rsplit("/application/", 1)[0]
    browser.get(authentik_base)
    time.sleep(1)
    browser.delete_all_cookies()

    browser.get(f"{gasket_url}/auth/login")
    time.sleep(2)  # Let the page load / redirect to Authentik

    if "authentik" not in browser.current_url.lower():
        return  # Already logged in or no redirect

    # Username stage
    uid_input = _wait_for_js(browser, JS_FIND_UID_INPUT, timeout=15)
    assert uid_input, f"Could not find username input. URL: {browser.current_url}"
    uid_input.clear()
    uid_input.send_keys(username)

    submit_btn = _wait_for_js(browser, JS_FIND_SUBMIT, timeout=5)
    assert submit_btn, "Could not find submit button on username stage"
    submit_btn.click()
    time.sleep(2)  # Wait for password stage

    # Password stage
    pw_input = _wait_for_js(browser, JS_FIND_PW_INPUT, timeout=15)
    assert pw_input, f"Could not find password input. URL: {browser.current_url}"
    pw_input.clear()
    pw_input.send_keys(password)

    submit_btn = _wait_for_js(browser, JS_FIND_SUBMIT, timeout=5)
    assert submit_btn, "Could not find submit button on password stage"
    submit_btn.click()

    # Wait for redirect back to Gasket (consent screen is disabled in provision.sh)
    deadline = time.time() + 15
    while time.time() < deadline:
        url = browser.current_url.lower()
        if "gasket" in url and "authentik" not in url:
            return
        time.sleep(0.5)

    pytest.fail(f"Did not redirect back to Gasket. Final URL: {browser.current_url}")


def create_authenticated_session(browser, gasket_url, username, password):
    """Log in via Selenium, extract cookies, and return a requests.Session.

    This enables API-level testing with a real OIDC session without needing
    the browser for every request.
    """
    authentik_login(browser, gasket_url, username, password)

    # Extract cookies from the browser and inject into a requests.Session
    session = requests.Session()
    session.verify = False  # Dev certs are self-signed
    for cookie in browser.get_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain", ""),
            path=cookie.get("path", "/"),
        )
    return session


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


@pytest.fixture(scope="session")
def user2_session(browser, gasket_url):
    """Authenticated requests.Session for user2 (gasket-users only).

    Performs a full Selenium login and extracts the session cookies.
    """
    return create_authenticated_session(browser, gasket_url, "user2", "password")


@pytest.fixture(scope="session")
def user3_session(browser, gasket_url):
    """Authenticated requests.Session for user3 (gasket-users + gasket-admins).

    Performs a full Selenium login and extracts the session cookies.
    """
    return create_authenticated_session(browser, gasket_url, "user3", "password")


@pytest.fixture
def anon_session():
    """Unauthenticated requests.Session (no cookies)."""
    session = requests.Session()
    session.verify = False
    return session


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
