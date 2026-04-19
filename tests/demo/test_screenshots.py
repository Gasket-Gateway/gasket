"""Selenium suite to capture automated demo screenshots."""

import os
import time
from selenium.webdriver.common.by import By

GASKET_URL = os.environ.get("GASKET_URL", "http://gasket:5000")

SCREENSHOT_DIR = "/results/screenshots"


def take_screenshot(browser, name):
    """Saves a screenshot to the designated directory."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    
    # Wait for any animations to finish (e.g. notifications, offcanvas)
    time.sleep(1)
    
    browser.save_screenshot(path)
    print(f"Captured: {path}")


def login_as(browser, role="admin"):
    """Bypasses Authentik UI and directly logs in via test session endpoint."""
    email = "demo-admin@localhost" if role == "admin" else "demo-user@localhost"
    groups = ["gasket-users", "gasket-admins"] if role == "admin" else ["gasket-users"]
    
    # We must hit a page on the domain first before setting cookies via JS or hitting endpoints
    browser.get(f"{GASKET_URL}/health")
    
    # Use the test session endpoint
    js = f"""
    fetch('/test/set-session', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            email: '{email}',
            name: 'Demo User',
            groups: {str(groups).replace("'", '"')}
        }})
    }});
    """
    browser.execute_script(js)
    time.sleep(0.5)


class TestAdminScreenshots:
    """Captures screenshots of the admin panel."""

    def test_capture_admin_status(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/admin/status")
        take_screenshot(browser, "admin_status")

    def test_capture_admin_backends(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/admin/backends")
        take_screenshot(browser, "admin_backends")

    def test_capture_admin_profiles(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/admin/profiles")
        take_screenshot(browser, "admin_profiles")

    def test_capture_admin_policies(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/admin/policies")
        take_screenshot(browser, "admin_policies")

    def test_capture_admin_keys(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/admin/keys")
        take_screenshot(browser, "admin_keys")

    def test_capture_admin_profiles_modal(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/admin/profiles")
        btn = browser.find_element(By.ID, "btn-add-profile")
        if btn:
            btn.click()
            time.sleep(0.5)
            take_screenshot(browser, "admin_profiles_modal_add")

    def test_capture_admin_backends_modal(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/admin/backends")
        btn = browser.find_element(By.ID, "btn-add-backend")
        if btn:
            btn.click()
            time.sleep(0.5)
            take_screenshot(browser, "admin_backends_modal_add")


class TestPortalScreenshots:
    """Captures screenshots of the user portal."""

    def test_capture_portal_dashboard(self, browser, mock_data):
        # We login as admin so we see the API keys created in the mock_data fixture
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/")
        take_screenshot(browser, "portal_dashboard")

    def test_capture_portal_keys(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/keys")
        take_screenshot(browser, "portal_keys")

    def test_capture_portal_profiles(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/profiles")
        take_screenshot(browser, "portal_profiles")

    def test_capture_portal_keys_modal(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/keys")
        btn = browser.find_element(By.ID, "portal-create-key-btn")
        if btn:
            btn.click()
            time.sleep(0.5)
            take_screenshot(browser, "portal_keys_modal_add")

    def test_capture_ui_demo(self, browser, mock_data):
        login_as(browser, "admin")
        browser.get(f"{GASKET_URL}/ui-demo")
        take_screenshot(browser, "ui_demo_top")
        
        # Scroll down and capture another section
        browser.execute_script("window.scrollTo(0, 1000);")
        time.sleep(0.5)
        take_screenshot(browser, "ui_demo_middle")
