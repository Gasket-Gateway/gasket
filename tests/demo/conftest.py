"""Fixtures for the automated screenshot demo suite."""

import os

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


GASKET_URL = os.environ.get("GASKET_URL", "http://gasket:5000")


@pytest.fixture(scope="session")
def browser():
    """Headless Chromium WebDriver (1920x1080) for capturing screenshots."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # Hide scrollbars for cleaner screenshots
    options.add_argument("--hide-scrollbars")
    
    # Force a specific user agent if needed
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    options.binary_location = chrome_bin

    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
    service = Service(executable_path=chromedriver_path)

    driver = webdriver.Chrome(service=service, options=options)
    
    # Set generous timeouts
    driver.implicitly_wait(5)
    driver.set_page_load_timeout(15)

    yield driver

    driver.quit()


@pytest.fixture(scope="module")
def admin_api_client():
    """An HTTP session logged in as an admin for setting up mock data."""
    sess = requests.Session()
    sess.verify = False
    resp = sess.post(
        f"{GASKET_URL}/test/set-session",
        json={
            "email": "demo-admin@localhost",
            "name": "Demo Admin",
            "groups": ["gasket-users", "gasket-admins"],
        },
    )
    assert resp.status_code == 200
    return sess


@pytest.fixture(scope="module")
def mock_data(admin_api_client):
    """Sets up realistic mock data for the screenshots and tears it down after."""
    # 1. Create Backends
    backends = []
    for name, url in [
        ("Production vLLM Cluster", "https://vllm.internal:8000"),
        ("Ollama Research (Llama 3)", "http://ollama.internal:11434"),
        ("OpenAI Fallback", "https://api.openai.com"),
    ]:
        resp = admin_api_client.post(
            f"{GASKET_URL}/admin/api/backends",
            json={"name": name, "base_url": url},
        )
        assert resp.status_code == 201
        backends.append(resp.json()["id"])
        
    # 2. Create Policies
    policies = []
    resp = admin_api_client.post(
        f"{GASKET_URL}/admin/api/policies",
        json={
            "name": "Acceptable Use Policy",
            "content": "Users must not use the AI models to generate harmful, illegal, or discriminatory content. All prompts are logged for compliance auditing.",
        },
    )
    assert resp.status_code == 201
    policies.append(resp.json()["id"])
    
    resp = admin_api_client.post(
        f"{GASKET_URL}/admin/api/policies",
        json={
            "name": "Data Privacy Addendum",
            "content": "Do not submit Personally Identifiable Information (PII) or Protected Health Information (PHI) to the external OpenAI fallback models.",
        },
    )
    assert resp.status_code == 201
    policies.append(resp.json()["id"])
    
    # 3. Create Profiles
    profiles = []
    resp = admin_api_client.post(
        f"{GASKET_URL}/admin/api/profiles",
        json={
            "name": "Engineering — Full Access",
            "description": "Unrestricted access to internal LLMs for development and research.",
            "policy_ids": policies,
            "backend_ids": backends[:2], # vllm and ollama
            "audit_content": True,
            "max_keys": 5,
        },
    )
    assert resp.status_code == 201
    profiles.append(resp.json()["id"])
    
    resp = admin_api_client.post(
        f"{GASKET_URL}/admin/api/profiles",
        json={
            "name": "Marketing Copywriter",
            "description": "Access to OpenAI fallback for drafting marketing materials.",
            "policy_ids": [policies[0]],
            "backend_ids": [backends[2]], # openai
            "audit_content": False,
            "max_keys": 2,
        },
    )
    assert resp.status_code == 201
    profiles.append(resp.json()["id"])

    # 3.5 Accept policies for the profile so we can create keys
    for policy_id in policies:
        resp = admin_api_client.post(
            f"{GASKET_URL}/admin/api/policies/{policy_id}/accept",
            json={"profile_id": profiles[0]},
        )
        assert resp.status_code == 201

    # 4. Create API Keys (for the admin user so we can see them in the portal)
    keys = []
    resp = admin_api_client.post(
        f"{GASKET_URL}/api/keys",
        json={
            "name": "Dev Script Testing",
            "profile_id": profiles[0],
            "vscode_continue": False,
        },
    )
    assert resp.status_code == 201
    keys.append(resp.json()["id"])
    
    resp = admin_api_client.post(
        f"{GASKET_URL}/api/keys",
        json={
            "name": "VSCode Continue Autocomplete",
            "profile_id": profiles[0],
            "vscode_continue": True,
        },
    )
    assert resp.status_code == 201
    keys.append(resp.json()["id"])

    yield

    # Teardown
    for k in keys:
        admin_api_client.delete(f"{GASKET_URL}/api/keys/{k}")
    for p in profiles:
        admin_api_client.delete(f"{GASKET_URL}/admin/api/profiles/{p}")
    for p in policies:
        admin_api_client.delete(f"{GASKET_URL}/admin/api/policies/{p}")
    for b in backends:
        admin_api_client.delete(f"{GASKET_URL}/admin/api/backends/{b}")
