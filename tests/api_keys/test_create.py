"""API key creation tests."""

from .conftest import accept_all_policies, create_test_profile_with_policy, cleanup_test_resources


class TestApiKeyCreate:
    """Verify API key creation."""

    def test_create_key_returns_201(self, client):
        policy, profile = create_test_profile_with_policy(client, "create-201")
        response = client.post("/api/keys", json={"name": "test-key-create", "profile_id": profile["id"]})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-key-create"
        assert data["profile_id"] == profile["id"]
        assert "key_value" in data
        assert data["key_value"].startswith("gsk_")
        assert data["revoked"] is False
        cleanup_test_resources(client, profile["id"], policy["id"], [data["id"]])

    def test_created_key_has_preview(self, client):
        policy, profile = create_test_profile_with_policy(client, "preview")
        response = client.post("/api/keys", json={"name": "test-key-preview", "profile_id": profile["id"]})
        data = response.json()
        assert "key_preview" in data
        assert data["key_preview"].startswith("gsk_…")
        assert len(data["key_preview"]) == len("gsk_…") + 4
        cleanup_test_resources(client, profile["id"], policy["id"], [data["id"]])

    def test_create_key_missing_name(self, client):
        policy, profile = create_test_profile_with_policy(client, "no-name")
        response = client.post("/api/keys", json={"profile_id": profile["id"]})
        assert response.status_code == 400
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_missing_profile(self, client):
        response = client.post("/api/keys", json={"name": "orphan-key"})
        assert response.status_code == 400

    def test_create_key_nonexistent_profile(self, client):
        response = client.post("/api/keys", json={"name": "bad-profile-key", "profile_id": 99999})
        assert response.status_code == 400

    def test_create_key_without_policy_acceptance(self, client):
        policy = client.post("/admin/api/policies", json={"name": "key-test-policy-unaccepted", "content": "Must accept me."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "key-test-profile-unaccepted", "policy_ids": [policy["id"]]}).json()
        response = client.post("/api/keys", json={"name": "should-fail", "profile_id": profile["id"]})
        assert response.status_code == 400
        assert "policies must be accepted" in response.json()["error"].lower() or "pending" in response.json()["error"].lower()
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_create_key_max_keys_enforcement(self, client):
        policy, profile = create_test_profile_with_policy(client, "max-keys")
        key_ids = []
        for i in range(3):
            resp = client.post("/api/keys", json={"name": f"max-test-{i}", "profile_id": profile["id"]})
            assert resp.status_code == 201
            key_ids.append(resp.json()["id"])
        response = client.post("/api/keys", json={"name": "max-test-overflow", "profile_id": profile["id"]})
        assert response.status_code == 400
        assert "maximum" in response.json()["error"].lower()
        cleanup_test_resources(client, profile["id"], policy["id"], key_ids)

    def test_create_key_with_vscode_continue(self, client):
        policy, profile = create_test_profile_with_policy(client, "vscode")
        response = client.post("/api/keys", json={"name": "vscode-key", "profile_id": profile["id"], "vscode_continue": True})
        assert response.status_code == 201
        assert response.json()["vscode_continue"] is True
        cleanup_test_resources(client, profile["id"], policy["id"], [response.json()["id"]])

    def test_create_key_open_webui_requires_profile_support(self, client):
        policy, profile = create_test_profile_with_policy(client, "webui-fail")
        response = client.post("/api/keys", json={"name": "webui-key", "profile_id": profile["id"], "open_webui": True})
        assert response.status_code == 400
        assert "open webui" in response.json()["error"].lower()
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_unique_values(self, client):
        policy, profile = create_test_profile_with_policy(client, "unique")
        key1 = client.post("/api/keys", json={"name": "unique-1", "profile_id": profile["id"]}).json()
        key2 = client.post("/api/keys", json={"name": "unique-2", "profile_id": profile["id"]}).json()
        assert key1["key_value"] != key2["key_value"]
        cleanup_test_resources(client, profile["id"], policy["id"], [key1["id"], key2["id"]])


class TestApiKeyCreateEdgeCases:
    """Edge cases for API key creation."""

    def test_create_key_whitespace_only_name(self, client):
        policy, profile = create_test_profile_with_policy(client, "ws-name")
        response = client.post("/api/keys", json={"name": "   ", "profile_id": profile["id"]})
        assert response.status_code == 400
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_empty_string_name(self, client):
        policy, profile = create_test_profile_with_policy(client, "empty-name")
        response = client.post("/api/keys", json={"name": "", "profile_id": profile["id"]})
        assert response.status_code == 400
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_no_json_body(self, client):
        response = client.post("/api/keys")
        assert response.status_code == 400

    def test_key_value_length(self, client):
        policy, profile = create_test_profile_with_policy(client, "key-len")
        create = client.post("/api/keys", json={"name": "len-test", "profile_id": profile["id"]}).json()
        assert len(create["key_value"]) == 52
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_key_value_hex_chars(self, client):
        policy, profile = create_test_profile_with_policy(client, "hex-check")
        create = client.post("/api/keys", json={"name": "hex-test", "profile_id": profile["id"]}).json()
        hex_part = create["key_value"][4:]
        int(hex_part, 16)
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_create_key_with_explicit_expiry(self, client):
        policy, profile = create_test_profile_with_policy(client, "expiry-set")
        response = client.post("/api/keys", json={"name": "expiry-test", "profile_id": profile["id"], "expires_at": "2099-12-31T23:59:59+00:00"})
        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None
        assert "2099" in data["expires_at"]
        assert data["is_expired"] is False
        cleanup_test_resources(client, profile["id"], policy["id"], [data["id"]])

    def test_create_key_with_past_expiry(self, client):
        policy, profile = create_test_profile_with_policy(client, "past-expiry")
        response = client.post("/api/keys", json={"name": "past-expiry-test", "profile_id": profile["id"], "expires_at": "2020-01-01T00:00:00+00:00"})
        assert response.status_code == 201
        assert response.json()["is_expired"] is True
        cleanup_test_resources(client, profile["id"], policy["id"], [response.json()["id"]])

    def test_create_key_invalid_expiry_format(self, client):
        policy, profile = create_test_profile_with_policy(client, "bad-expiry")
        response = client.post("/api/keys", json={"name": "bad-expiry-test", "profile_id": profile["id"], "expires_at": "not-a-date"})
        assert response.status_code == 400
        cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_profile_no_policies(self, client):
        profile = client.post("/admin/api/profiles", json={"name": "key-test-profile-no-policies", "max_keys_per_user": 3}).json()
        response = client.post("/api/keys", json={"name": "no-policy-key", "profile_id": profile["id"]})
        assert response.status_code == 201
        cleanup_test_resources(client, profile["id"], None, [response.json()["id"]])
        client.delete(f"/admin/api/profiles/{profile['id']}")

    def test_create_key_defaults_vscode_false(self, client):
        policy, profile = create_test_profile_with_policy(client, "default-flags")
        create = client.post("/api/keys", json={"name": "defaults-test", "profile_id": profile["id"]}).json()
        assert create["vscode_continue"] is False
        assert create["open_webui"] is False
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_create_key_no_expiry_default(self, client):
        policy, profile = create_test_profile_with_policy(client, "no-expiry")
        create = client.post("/api/keys", json={"name": "no-expiry-test", "profile_id": profile["id"]}).json()
        assert create["expires_at"] is None
        assert create["is_expired"] is False
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])
