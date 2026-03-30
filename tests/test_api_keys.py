"""API key management tests — CRUD, revocation, policy gating, and lifecycle.

Run against the Gasket test environment (GASKET_TEST_MODE) where the user
session is user3@localhost with groups gasket-users and gasket-admins.

Config-defined profile 'internal-standard' and policy 'acceptable-use' are
seeded on startup from config.yaml.
"""


# ─── Helpers ───────────────────────────────────────────────────────


def _accept_all_policies(client, profile_id):
    """Accept all pending policies for a profile as the test user."""
    check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
    for pending in check.get("pending", []):
        client.post(
            f"/admin/api/policies/{pending['policy_id']}/accept",
            json={"profile_id": profile_id},
        )


def _create_test_profile_with_policy(client, name_suffix="1"):
    """Create a policy, a profile linked to it, and accept the policy.

    Returns (policy_dict, profile_dict).
    """
    policy = client.post(
        "/admin/api/policies",
        json={
            "name": f"key-test-policy-{name_suffix}",
            "content": f"Test policy content {name_suffix}.",
        },
    ).json()

    profile = client.post(
        "/admin/api/profiles",
        json={
            "name": f"key-test-profile-{name_suffix}",
            "policy_ids": [policy["id"]],
            "max_keys_per_user": 3,
        },
    ).json()

    _accept_all_policies(client, profile["id"])
    return policy, profile


def _cleanup_test_resources(client, profile_id, policy_id, key_ids=None):
    """Clean up test resources."""
    if key_ids:
        for key_id in key_ids:
            client.post(f"/api/keys/{key_id}/revoke")
    client.delete(f"/admin/api/profiles/{profile_id}")
    client.delete(f"/admin/api/policies/{policy_id}")


class TestApiKeysList:
    """Verify the user key listing API."""

    def test_list_keys_returns_200(self, client):
        """GET /api/keys should return 200."""
        response = client.get("/api/keys")
        assert response.status_code == 200

    def test_list_keys_returns_json_list(self, client):
        """GET /api/keys should return a JSON list."""
        response = client.get("/api/keys")
        data = response.json()
        assert isinstance(data, list)


class TestApiKeyCreate:
    """Verify API key creation."""

    def test_create_key_returns_201(self, client):
        """POST /api/keys should create a key and return 201."""
        policy, profile = _create_test_profile_with_policy(client, "create-201")

        response = client.post(
            "/api/keys",
            json={
                "name": "test-key-create",
                "profile_id": profile["id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-key-create"
        assert data["profile_id"] == profile["id"]
        assert "key_value" in data  # Full key revealed on creation
        assert data["key_value"].startswith("gsk_")
        assert data["revoked"] is False

        _cleanup_test_resources(client, profile["id"], policy["id"], [data["id"]])

    def test_created_key_has_preview(self, client):
        """Created key should have a masked preview."""
        policy, profile = _create_test_profile_with_policy(client, "preview")

        response = client.post(
            "/api/keys",
            json={"name": "test-key-preview", "profile_id": profile["id"]},
        )
        data = response.json()
        assert "key_preview" in data
        assert data["key_preview"].startswith("gsk_…")
        assert len(data["key_preview"]) == len("gsk_…") + 4  # 4 char suffix

        _cleanup_test_resources(client, profile["id"], policy["id"], [data["id"]])

    def test_create_key_missing_name(self, client):
        """Creating without a name should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "no-name")

        response = client.post(
            "/api/keys",
            json={"profile_id": profile["id"]},
        )
        assert response.status_code == 400

        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_missing_profile(self, client):
        """Creating without a profile_id should return 400."""
        response = client.post(
            "/api/keys",
            json={"name": "orphan-key"},
        )
        assert response.status_code == 400

    def test_create_key_nonexistent_profile(self, client):
        """Creating with a non-existent profile should return 400."""
        response = client.post(
            "/api/keys",
            json={"name": "bad-profile-key", "profile_id": 99999},
        )
        assert response.status_code == 400

    def test_create_key_without_policy_acceptance(self, client):
        """Creating a key without accepting policies should return 400."""
        # Create policy and profile but DO NOT accept
        policy = client.post(
            "/admin/api/policies",
            json={
                "name": "key-test-policy-unaccepted",
                "content": "Must accept me.",
            },
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "key-test-profile-unaccepted",
                "policy_ids": [policy["id"]],
            },
        ).json()

        response = client.post(
            "/api/keys",
            json={"name": "should-fail", "profile_id": profile["id"]},
        )
        assert response.status_code == 400
        assert "policies must be accepted" in response.json()["error"].lower() or \
               "pending" in response.json()["error"].lower()

        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_create_key_max_keys_enforcement(self, client):
        """Exceeding max_keys_per_user should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "max-keys")
        # Profile has max_keys_per_user=3

        key_ids = []
        for i in range(3):
            resp = client.post(
                "/api/keys",
                json={"name": f"max-test-{i}", "profile_id": profile["id"]},
            )
            assert resp.status_code == 201
            key_ids.append(resp.json()["id"])

        # 4th key should fail
        response = client.post(
            "/api/keys",
            json={"name": "max-test-overflow", "profile_id": profile["id"]},
        )
        assert response.status_code == 400
        assert "maximum" in response.json()["error"].lower()

        _cleanup_test_resources(client, profile["id"], policy["id"], key_ids)

    def test_create_key_with_vscode_continue(self, client):
        """Creating with vscode_continue=True should set the flag."""
        policy, profile = _create_test_profile_with_policy(client, "vscode")

        response = client.post(
            "/api/keys",
            json={
                "name": "vscode-key",
                "profile_id": profile["id"],
                "vscode_continue": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["vscode_continue"] is True

        _cleanup_test_resources(client, profile["id"], policy["id"], [response.json()["id"]])

    def test_create_key_open_webui_requires_profile_support(self, client):
        """Creating with open_webui=True on an unsupported profile should fail."""
        policy, profile = _create_test_profile_with_policy(client, "webui-fail")
        # Default profile has open_webui_enabled=False

        response = client.post(
            "/api/keys",
            json={
                "name": "webui-key",
                "profile_id": profile["id"],
                "open_webui": True,
            },
        )
        assert response.status_code == 400
        assert "open webui" in response.json()["error"].lower()

        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_unique_values(self, client):
        """Each created key should have a unique key_value."""
        policy, profile = _create_test_profile_with_policy(client, "unique")

        key1 = client.post(
            "/api/keys",
            json={"name": "unique-1", "profile_id": profile["id"]},
        ).json()
        key2 = client.post(
            "/api/keys",
            json={"name": "unique-2", "profile_id": profile["id"]},
        ).json()

        assert key1["key_value"] != key2["key_value"]

        _cleanup_test_resources(client, profile["id"], policy["id"],
                               [key1["id"], key2["id"]])


class TestApiKeyRead:
    """Verify API key read operations."""

    def test_get_own_key(self, client):
        """GET /api/keys/<id> should return the key for the owner."""
        policy, profile = _create_test_profile_with_policy(client, "read")

        create = client.post(
            "/api/keys",
            json={"name": "read-test", "profile_id": profile["id"]},
        ).json()

        response = client.get(f"/api/keys/{create['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "read-test"
        # Default GET does not reveal the full key
        assert "key_value" not in data

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_get_key_not_found(self, client):
        """GET for a non-existent key should return 404."""
        response = client.get("/api/keys/99999")
        assert response.status_code == 404


class TestApiKeyReveal:
    """Verify the key reveal endpoint."""

    def test_reveal_own_key(self, client):
        """GET /api/keys/<id>/reveal should return the full key value."""
        policy, profile = _create_test_profile_with_policy(client, "reveal")

        create = client.post(
            "/api/keys",
            json={"name": "reveal-test", "profile_id": profile["id"]},
        ).json()
        original_key = create["key_value"]

        response = client.get(f"/api/keys/{create['id']}/reveal")
        assert response.status_code == 200
        data = response.json()
        assert "key_value" in data
        assert data["key_value"] == original_key
        assert data["key_value"].startswith("gsk_")

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_reveal_not_found(self, client):
        """Reveal for a non-existent key should return 404."""
        response = client.get("/api/keys/99999/reveal")
        assert response.status_code == 404


class TestApiKeyEdit:
    """Verify API key editing."""

    def test_edit_vscode_continue(self, client):
        """PUT /api/keys/<id> should toggle vscode_continue."""
        policy, profile = _create_test_profile_with_policy(client, "edit-vscode")

        create = client.post(
            "/api/keys",
            json={"name": "edit-vscode-test", "profile_id": profile["id"]},
        ).json()
        assert create["vscode_continue"] is False

        response = client.put(
            f"/api/keys/{create['id']}",
            json={"vscode_continue": True},
        )
        assert response.status_code == 200
        assert response.json()["vscode_continue"] is True

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_edit_not_found(self, client):
        """PUT for a non-existent key should return 404."""
        response = client.put(
            "/api/keys/99999",
            json={"vscode_continue": True},
        )
        assert response.status_code == 404


class TestApiKeyRevoke:
    """Verify API key revocation."""

    def test_revoke_own_key(self, client):
        """POST /api/keys/<id>/revoke should revoke the key."""
        policy, profile = _create_test_profile_with_policy(client, "revoke")

        create = client.post(
            "/api/keys",
            json={"name": "revoke-test", "profile_id": profile["id"]},
        ).json()

        response = client.post(f"/api/keys/{create['id']}/revoke")
        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is True
        assert data["revoked_at"] is not None
        assert data["revoked_by"] is not None

        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_revoke_already_revoked(self, client):
        """Revoking an already-revoked key should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "double-revoke")

        create = client.post(
            "/api/keys",
            json={"name": "double-revoke-test", "profile_id": profile["id"]},
        ).json()

        client.post(f"/api/keys/{create['id']}/revoke")
        response = client.post(f"/api/keys/{create['id']}/revoke")
        assert response.status_code == 400

        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_revoke_not_found(self, client):
        """Revoking a non-existent key should return 404."""
        response = client.post("/api/keys/99999/revoke")
        assert response.status_code == 404

    def test_revoked_key_doesnt_count_towards_max(self, client):
        """Revoked keys should not count towards the max_keys_per_user limit."""
        policy, profile = _create_test_profile_with_policy(client, "revoke-max")
        # max_keys_per_user = 3

        key_ids = []
        for i in range(3):
            resp = client.post(
                "/api/keys",
                json={"name": f"revoke-max-{i}", "profile_id": profile["id"]},
            )
            key_ids.append(resp.json()["id"])

        # Revoke one key
        client.post(f"/api/keys/{key_ids[0]}/revoke")

        # Should now be able to create another
        resp = client.post(
            "/api/keys",
            json={"name": "revoke-max-replacement", "profile_id": profile["id"]},
        )
        assert resp.status_code == 201
        key_ids.append(resp.json()["id"])

        _cleanup_test_resources(client, profile["id"], policy["id"], key_ids[1:])


class TestApiKeyAdminManagement:
    """Verify admin API key management routes."""

    def test_admin_list_keys(self, client):
        """GET /admin/api/keys should return 200."""
        response = client.get("/admin/api/keys")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_list_keys_user_filter(self, client):
        """GET /admin/api/keys?user= should filter by user."""
        response = client.get("/admin/api/keys?user=nonexistent@test.com")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_admin_list_keys_profile_filter(self, client):
        """GET /admin/api/keys?profile_id= should filter by profile."""
        response = client.get("/admin/api/keys?profile_id=99999")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_admin_get_key_masked(self, client):
        """Admin GET should return the key without the full key value."""
        policy, profile = _create_test_profile_with_policy(client, "admin-get")

        create = client.post(
            "/api/keys",
            json={"name": "admin-get-test", "profile_id": profile["id"]},
        ).json()

        response = client.get(f"/admin/api/keys/{create['id']}")
        assert response.status_code == 200
        data = response.json()
        assert "key_value" not in data
        assert "key_preview" in data
        assert data["key_preview"].startswith("gsk_…")

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_list_keys_masked(self, client):
        """Admin list should never include full key values."""
        policy, profile = _create_test_profile_with_policy(client, "admin-list-mask")

        create = client.post(
            "/api/keys",
            json={"name": "admin-list-mask-test", "profile_id": profile["id"]},
        ).json()

        response = client.get("/admin/api/keys")
        keys = response.json()

        # Find the created key
        our_key = next(k for k in keys if k["id"] == create["id"])
        assert "key_value" not in our_key
        assert our_key["key_preview"].startswith("gsk_…")

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_get_key_not_found(self, client):
        """Admin GET for a non-existent key should return 404."""
        response = client.get("/admin/api/keys/99999")
        assert response.status_code == 404

    def test_admin_revoke_key(self, client):
        """Admin should be able to revoke any key."""
        policy, profile = _create_test_profile_with_policy(client, "admin-revoke")

        create = client.post(
            "/api/keys",
            json={"name": "admin-revoke-test", "profile_id": profile["id"]},
        ).json()

        response = client.post(f"/admin/api/keys/{create['id']}/revoke")
        assert response.status_code == 200
        assert response.json()["revoked"] is True

        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_admin_restore_key(self, client):
        """Admin should be able to restore a revoked key."""
        policy, profile = _create_test_profile_with_policy(client, "admin-restore")

        create = client.post(
            "/api/keys",
            json={"name": "admin-restore-test", "profile_id": profile["id"]},
        ).json()

        # Revoke then restore
        client.post(f"/admin/api/keys/{create['id']}/revoke")
        response = client.post(f"/admin/api/keys/{create['id']}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is False
        assert data["revoked_at"] is None
        assert data["revoked_by"] is None

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_restore_non_revoked_key(self, client):
        """Restoring a non-revoked key should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "restore-fail")

        create = client.post(
            "/api/keys",
            json={"name": "restore-fail-test", "profile_id": profile["id"]},
        ).json()

        response = client.post(f"/admin/api/keys/{create['id']}/restore")
        assert response.status_code == 400

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_restore_expired_key_fails(self, client):
        """Restoring an expired key should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "restore-expired")

        # Create a key that has already expired
        response = client.post(
            "/api/keys",
            json={
                "name": "expired-key",
                "profile_id": profile["id"],
                "expires_at": "2020-01-01T00:00:00+00:00",
            },
        )
        assert response.status_code == 201
        key_id = response.json()["id"]

        # Revoke it
        client.post(f"/admin/api/keys/{key_id}/revoke")

        # Try to restore — should fail because it's expired
        response = client.post(f"/admin/api/keys/{key_id}/restore")
        assert response.status_code == 400
        assert "expired" in response.json()["error"].lower()

        _cleanup_test_resources(client, profile["id"], policy["id"])


class TestApiKeyPolicySnapshots:
    """Verify policy version snapshots on API keys."""

    def test_key_has_policy_snapshots(self, client):
        """Created key should snapshot the accepted policy versions."""
        policy, profile = _create_test_profile_with_policy(client, "snapshot")

        create = client.post(
            "/api/keys",
            json={"name": "snapshot-test", "profile_id": profile["id"]},
        ).json()

        assert len(create["policy_snapshot_ids"]) > 0

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_key_policy_snapshots_endpoint(self, client):
        """GET /api/keys/<id>/policies should return snapshot details."""
        policy, profile = _create_test_profile_with_policy(client, "snap-ep")

        create = client.post(
            "/api/keys",
            json={"name": "snap-ep-test", "profile_id": profile["id"]},
        ).json()

        response = client.get(f"/api/keys/{create['id']}/policies")
        assert response.status_code == 200
        snapshots = response.json()
        assert isinstance(snapshots, list)
        assert len(snapshots) > 0
        assert "policy_name" in snapshots[0]
        assert "version_number" in snapshots[0]

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_key_policy_snapshots(self, client):
        """Admin GET /admin/api/keys/<id>/policies should return snapshots."""
        policy, profile = _create_test_profile_with_policy(client, "admin-snap")

        create = client.post(
            "/api/keys",
            json={"name": "admin-snap-test", "profile_id": profile["id"]},
        ).json()

        response = client.get(f"/admin/api/keys/{create['id']}/policies")
        assert response.status_code == 200
        snapshots = response.json()
        assert len(snapshots) > 0

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_policy_snapshot_records_correct_version(self, client):
        """Snapshot should record the version at time of key creation, not later versions."""
        # Create policy with v1
        policy = client.post(
            "/admin/api/policies",
            json={
                "name": "key-test-policy-snap-version",
                "content": "Version 1.",
            },
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "key-test-profile-snap-version",
                "policy_ids": [policy["id"]],
            },
        ).json()

        # Accept v1
        _accept_all_policies(client, profile["id"])

        # Create key (should snapshot v1)
        create = client.post(
            "/api/keys",
            json={"name": "snap-version-test", "profile_id": profile["id"]},
        ).json()

        # Now update policy to v2
        client.put(
            f"/admin/api/policies/{policy['id']}",
            json={"content": "Version 2."},
        )

        # Key's snapshot should still be v1
        snapshots = client.get(f"/api/keys/{create['id']}/policies").json()
        assert len(snapshots) == 1
        assert snapshots[0]["version_number"] == 1

        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])


class TestApiKeyLifecycle:
    """Full lifecycle test: accept policies → create key → edit → revoke."""

    def test_full_lifecycle(self, client):
        """Exercise the complete API key lifecycle."""
        # 1. Create policy and profile
        policy = client.post(
            "/admin/api/policies",
            json={
                "name": "lifecycle-key-policy",
                "content": "Accept this policy.",
            },
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "lifecycle-key-profile",
                "policy_ids": [policy["id"]],
                "max_keys_per_user": 5,
            },
        ).json()

        # 2. Try to create key without acceptance — should fail
        resp = client.post(
            "/api/keys",
            json={"name": "lifecycle-key", "profile_id": profile["id"]},
        )
        assert resp.status_code == 400

        # 3. Accept the policy
        _accept_all_policies(client, profile["id"])

        # 4. Create the key
        create = client.post(
            "/api/keys",
            json={
                "name": "lifecycle-key",
                "profile_id": profile["id"],
                "vscode_continue": False,
            },
        )
        assert create.status_code == 201
        key_data = create.json()
        key_id = key_data["id"]
        assert key_data["key_value"].startswith("gsk_")
        assert key_data["vscode_continue"] is False

        # 5. Verify it appears in user list
        keys = client.get("/api/keys").json()
        key_ids = [k["id"] for k in keys]
        assert key_id in key_ids

        # 6. Get key detail (masked)
        detail = client.get(f"/api/keys/{key_id}").json()
        assert "key_value" not in detail
        assert detail["key_preview"].startswith("gsk_…")

        # 7. Reveal full key
        revealed = client.get(f"/api/keys/{key_id}/reveal").json()
        assert revealed["key_value"] == key_data["key_value"]

        # 8. Edit the key
        edit = client.put(
            f"/api/keys/{key_id}",
            json={"vscode_continue": True},
        )
        assert edit.status_code == 200
        assert edit.json()["vscode_continue"] is True

        # 9. Check policy snapshots
        snapshots = client.get(f"/api/keys/{key_id}/policies").json()
        assert len(snapshots) >= 1

        # 10. Admin can see it (masked)
        admin_detail = client.get(f"/admin/api/keys/{key_id}").json()
        assert "key_value" not in admin_detail

        # 11. User revokes
        revoke = client.post(f"/api/keys/{key_id}/revoke")
        assert revoke.status_code == 200
        assert revoke.json()["revoked"] is True

        # 12. Admin restores
        restore = client.post(f"/admin/api/keys/{key_id}/restore")
        assert restore.status_code == 200
        assert restore.json()["revoked"] is False

        # 13. Revoke again for cleanup
        client.post(f"/api/keys/{key_id}/revoke")

        # 14. Clean up
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")


class TestApiKeyWithConfigProfile:
    """Verify keys work with the config-seeded internal-standard profile."""

    def test_create_key_for_config_profile(self, client):
        """Creating a key for the config profile should work after accepting policies."""
        # Find the config profile
        profiles = client.get("/admin/api/profiles").json()
        config_profile = next(p for p in profiles if p["name"] == "internal-standard")

        # Accept all policies
        _accept_all_policies(client, config_profile["id"])

        # Create a key
        response = client.post(
            "/api/keys",
            json={
                "name": "config-profile-key",
                "profile_id": config_profile["id"],
            },
        )
        assert response.status_code == 201
        key_data = response.json()
        assert key_data["profile_name"] == "internal-standard"
        assert key_data["key_value"].startswith("gsk_")

        # Clean up — revoke the key
        client.post(f"/api/keys/{key_data['id']}/revoke")


# ─── Edge Cases ────────────────────────────────────────────────────


class TestApiKeyCreateEdgeCases:
    """Edge cases for API key creation."""

    def test_create_key_whitespace_only_name(self, client):
        """Creating with a whitespace-only name should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "ws-name")
        response = client.post(
            "/api/keys",
            json={"name": "   ", "profile_id": profile["id"]},
        )
        assert response.status_code == 400
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_empty_string_name(self, client):
        """Creating with an empty string name should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "empty-name")
        response = client.post(
            "/api/keys",
            json={"name": "", "profile_id": profile["id"]},
        )
        assert response.status_code == 400
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_no_json_body(self, client):
        """POST with no JSON body should return 400."""
        response = client.post("/api/keys")
        assert response.status_code == 400

    def test_key_value_length(self, client):
        """Generated key should be gsk_ prefix + 48 hex chars = 52 chars total."""
        policy, profile = _create_test_profile_with_policy(client, "key-len")
        create = client.post(
            "/api/keys",
            json={"name": "len-test", "profile_id": profile["id"]},
        ).json()
        assert len(create["key_value"]) == 52  # "gsk_" (4) + 48 hex chars
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_key_value_hex_chars(self, client):
        """Key suffix (after gsk_) should be valid hex characters."""
        policy, profile = _create_test_profile_with_policy(client, "hex-check")
        create = client.post(
            "/api/keys",
            json={"name": "hex-test", "profile_id": profile["id"]},
        ).json()
        hex_part = create["key_value"][4:]  # strip "gsk_"
        int(hex_part, 16)  # Raises ValueError if not valid hex
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_create_key_with_explicit_expiry(self, client):
        """Creating with an explicit expires_at should set the expiry."""
        policy, profile = _create_test_profile_with_policy(client, "expiry-set")
        response = client.post(
            "/api/keys",
            json={
                "name": "expiry-test",
                "profile_id": profile["id"],
                "expires_at": "2099-12-31T23:59:59+00:00",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None
        assert "2099" in data["expires_at"]
        assert data["is_expired"] is False
        _cleanup_test_resources(client, profile["id"], policy["id"], [data["id"]])

    def test_create_key_with_past_expiry(self, client):
        """Creating with an already-passed expiry should succeed but mark as expired."""
        policy, profile = _create_test_profile_with_policy(client, "past-expiry")
        response = client.post(
            "/api/keys",
            json={
                "name": "past-expiry-test",
                "profile_id": profile["id"],
                "expires_at": "2020-01-01T00:00:00+00:00",
            },
        )
        assert response.status_code == 201
        assert response.json()["is_expired"] is True
        _cleanup_test_resources(client, profile["id"], policy["id"], [response.json()["id"]])

    def test_create_key_invalid_expiry_format(self, client):
        """Creating with an invalid expires_at format should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "bad-expiry")
        response = client.post(
            "/api/keys",
            json={
                "name": "bad-expiry-test",
                "profile_id": profile["id"],
                "expires_at": "not-a-date",
            },
        )
        assert response.status_code == 400
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_create_key_profile_no_policies(self, client):
        """Creating a key on a profile with no policies should succeed without gating."""
        profile = client.post(
            "/admin/api/profiles",
            json={"name": "key-test-profile-no-policies", "max_keys_per_user": 3},
        ).json()

        response = client.post(
            "/api/keys",
            json={"name": "no-policy-key", "profile_id": profile["id"]},
        )
        assert response.status_code == 201

        _cleanup_test_resources(client, profile["id"], None, [response.json()["id"]])
        # profile cleanup already done above, just delete profile
        client.delete(f"/admin/api/profiles/{profile['id']}")

    def test_create_key_defaults_vscode_false(self, client):
        """Keys should default vscode_continue to False."""
        policy, profile = _create_test_profile_with_policy(client, "default-flags")
        create = client.post(
            "/api/keys",
            json={"name": "defaults-test", "profile_id": profile["id"]},
        ).json()
        assert create["vscode_continue"] is False
        assert create["open_webui"] is False
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_create_key_no_expiry_default(self, client):
        """Keys with no expiry config should have expires_at=None."""
        policy, profile = _create_test_profile_with_policy(client, "no-expiry")
        create = client.post(
            "/api/keys",
            json={"name": "no-expiry-test", "profile_id": profile["id"]},
        ).json()
        assert create["expires_at"] is None
        assert create["is_expired"] is False
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])


class TestApiKeyReadEdgeCases:
    """Edge cases for API key reading."""

    def test_get_key_includes_profile_name(self, client):
        """Key detail should include the profile name."""
        policy, profile = _create_test_profile_with_policy(client, "read-profile")
        create = client.post(
            "/api/keys",
            json={"name": "profile-name-test", "profile_id": profile["id"]},
        ).json()

        detail = client.get(f"/api/keys/{create['id']}").json()
        assert detail["profile_name"] == f"key-test-profile-read-profile"
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_get_key_has_all_expected_fields(self, client):
        """Key detail should have all the expected response fields."""
        policy, profile = _create_test_profile_with_policy(client, "fields")
        create = client.post(
            "/api/keys",
            json={"name": "fields-test", "profile_id": profile["id"]},
        ).json()

        detail = client.get(f"/api/keys/{create['id']}").json()
        expected_fields = [
            "id", "user_email", "name", "key_preview", "profile_id",
            "profile_name", "expires_at", "is_expired", "revoked",
            "revoked_at", "revoked_by", "vscode_continue", "open_webui",
            "created_at", "policy_snapshot_ids",
        ]
        for field in expected_fields:
            assert field in detail, f"Missing field: {field}"
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_reveal_revoked_key_still_works(self, client):
        """Users should be able to reveal the value of a revoked key they own."""
        policy, profile = _create_test_profile_with_policy(client, "reveal-revoked")
        create = client.post(
            "/api/keys",
            json={"name": "reveal-revoked-test", "profile_id": profile["id"]},
        ).json()
        original_key = create["key_value"]

        client.post(f"/api/keys/{create['id']}/revoke")

        response = client.get(f"/api/keys/{create['id']}/reveal")
        assert response.status_code == 200
        assert response.json()["key_value"] == original_key
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_list_keys_includes_revoked(self, client):
        """User key list should include revoked keys."""
        policy, profile = _create_test_profile_with_policy(client, "list-revoked")
        create = client.post(
            "/api/keys",
            json={"name": "list-revoked-test", "profile_id": profile["id"]},
        ).json()
        client.post(f"/api/keys/{create['id']}/revoke")

        keys = client.get("/api/keys").json()
        our_key = next((k for k in keys if k["id"] == create["id"]), None)
        assert our_key is not None
        assert our_key["revoked"] is True
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_key_preview_matches_key_value_suffix(self, client):
        """The key_preview last 4 chars should match the key_value's last 4 chars."""
        policy, profile = _create_test_profile_with_policy(client, "preview-match")
        create = client.post(
            "/api/keys",
            json={"name": "preview-match-test", "profile_id": profile["id"]},
        ).json()

        full_key = create["key_value"]
        preview = create["key_preview"]
        assert preview == f"gsk_…{full_key[-4:]}"
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])


class TestApiKeyEditEdgeCases:
    """Edge cases for API key editing."""

    def test_edit_toggle_vscode_on_and_off(self, client):
        """Should be able to toggle vscode_continue on then off again."""
        policy, profile = _create_test_profile_with_policy(client, "toggle-vsc")
        create = client.post(
            "/api/keys",
            json={"name": "toggle-test", "profile_id": profile["id"]},
        ).json()

        client.put(f"/api/keys/{create['id']}", json={"vscode_continue": True})
        resp = client.put(f"/api/keys/{create['id']}", json={"vscode_continue": False})
        assert resp.status_code == 200
        assert resp.json()["vscode_continue"] is False
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_edit_no_json_body(self, client):
        """PUT with no JSON body should return 400."""
        policy, profile = _create_test_profile_with_policy(client, "edit-nobody")
        create = client.post(
            "/api/keys",
            json={"name": "edit-nobody-test", "profile_id": profile["id"]},
        ).json()
        response = client.put(f"/api/keys/{create['id']}")
        assert response.status_code == 400
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_edit_does_not_change_name(self, client):
        """Edit should not allow changing the key name — it should be ignored."""
        policy, profile = _create_test_profile_with_policy(client, "edit-noname")
        create = client.post(
            "/api/keys",
            json={"name": "original-name", "profile_id": profile["id"]},
        ).json()

        client.put(f"/api/keys/{create['id']}", json={"name": "new-name"})
        detail = client.get(f"/api/keys/{create['id']}").json()
        assert detail["name"] == "original-name"
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])


class TestApiKeyRevokeEdgeCases:
    """Edge cases for revocation and restoration."""

    def test_revoke_records_revoker_email(self, client):
        """Revocation should record who revoked the key."""
        policy, profile = _create_test_profile_with_policy(client, "revoker-email")
        create = client.post(
            "/api/keys",
            json={"name": "revoker-test", "profile_id": profile["id"]},
        ).json()

        revoke = client.post(f"/api/keys/{create['id']}/revoke")
        assert revoke.json()["revoked_by"] == "user3@localhost"
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_admin_revoke_records_admin_email(self, client):
        """Admin revocation should record the admin's email as revoker."""
        policy, profile = _create_test_profile_with_policy(client, "admin-revoker")
        create = client.post(
            "/api/keys",
            json={"name": "admin-revoker-test", "profile_id": profile["id"]},
        ).json()

        revoke = client.post(f"/admin/api/keys/{create['id']}/revoke")
        assert revoke.json()["revoked_by"] == "user3@localhost"
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_restore_then_revoke_again(self, client):
        """A restored key should be revokable again."""
        policy, profile = _create_test_profile_with_policy(client, "re-revoke")
        create = client.post(
            "/api/keys",
            json={"name": "re-revoke-test", "profile_id": profile["id"]},
        ).json()

        client.post(f"/admin/api/keys/{create['id']}/revoke")
        client.post(f"/admin/api/keys/{create['id']}/restore")
        revoke2 = client.post(f"/api/keys/{create['id']}/revoke")
        assert revoke2.status_code == 200
        assert revoke2.json()["revoked"] is True
        _cleanup_test_resources(client, profile["id"], policy["id"])

    def test_admin_revoke_not_found(self, client):
        """Admin revoking a non-existent key should return 400."""
        response = client.post("/admin/api/keys/99999/revoke")
        assert response.status_code == 400

    def test_admin_restore_not_found(self, client):
        """Admin restoring a non-existent key should return 400."""
        response = client.post("/admin/api/keys/99999/restore")
        assert response.status_code == 400


class TestApiKeyAdminEdgeCases:
    """Edge cases for admin key management."""

    def test_admin_list_with_both_filters(self, client):
        """Admin list with both user and profile_id filters should work."""
        policy, profile = _create_test_profile_with_policy(client, "both-filters")
        create = client.post(
            "/api/keys",
            json={"name": "both-filters-test", "profile_id": profile["id"]},
        ).json()

        response = client.get(
            f"/admin/api/keys?user=user3@localhost&profile_id={profile['id']}"
        )
        assert response.status_code == 200
        keys = response.json()
        assert any(k["id"] == create["id"] for k in keys)
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_list_user_filter_matches_keys(self, client):
        """Admin filtering by the test user should return their keys."""
        policy, profile = _create_test_profile_with_policy(client, "user-filter")
        create = client.post(
            "/api/keys",
            json={"name": "user-filter-test", "profile_id": profile["id"]},
        ).json()

        response = client.get("/admin/api/keys?user=user3@localhost")
        keys = response.json()
        assert any(k["id"] == create["id"] for k in keys)
        _cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_policy_snapshots_not_found(self, client):
        """Admin policy snapshots for a non-existent key should return 404."""
        response = client.get("/admin/api/keys/99999/policies")
        assert response.status_code == 404

    def test_user_policy_snapshots_not_found(self, client):
        """User policy snapshots for a non-existent key should return 404."""
        response = client.get("/api/keys/99999/policies")
        assert response.status_code == 404


class TestApiKeyMultiplePolicies:
    """Verify key creation and snapshots with multiple policies on a profile."""

    def test_create_key_requires_all_policies_accepted(self, client):
        """If a profile has 2 policies, both must be accepted."""
        p1 = client.post(
            "/admin/api/policies",
            json={"name": "multi-pol-1", "content": "Policy 1."},
        ).json()
        p2 = client.post(
            "/admin/api/policies",
            json={"name": "multi-pol-2", "content": "Policy 2."},
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "multi-pol-profile",
                "policy_ids": [p1["id"], p2["id"]],
                "max_keys_per_user": 3,
            },
        ).json()

        # Accept only the first policy
        client.post(
            f"/admin/api/policies/{p1['id']}/accept",
            json={"profile_id": profile["id"]},
        )

        # Should fail — p2 still pending
        response = client.post(
            "/api/keys",
            json={"name": "partial-accept-key", "profile_id": profile["id"]},
        )
        assert response.status_code == 400

        # Accept the second policy too
        client.post(
            f"/admin/api/policies/{p2['id']}/accept",
            json={"profile_id": profile["id"]},
        )

        # Should succeed now
        response = client.post(
            "/api/keys",
            json={"name": "full-accept-key", "profile_id": profile["id"]},
        )
        assert response.status_code == 201

        # Snapshot should include both policies
        snapshots = client.get(
            f"/api/keys/{response.json()['id']}/policies"
        ).json()
        assert len(snapshots) == 2
        snap_names = {s["policy_name"] for s in snapshots}
        assert "multi-pol-1" in snap_names
        assert "multi-pol-2" in snap_names

        # Cleanup
        client.post(f"/api/keys/{response.json()['id']}/revoke")
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{p1['id']}")
        client.delete(f"/admin/api/policies/{p2['id']}")

    def test_policy_reacceptance_blocks_new_keys(self, client):
        """After policy reacceptance invalidation, new key creation should be blocked."""
        policy = client.post(
            "/admin/api/policies",
            json={
                "name": "reaccept-block-pol",
                "content": "Version 1.",
                "enforce_reacceptance": True,
            },
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "reaccept-block-profile",
                "policy_ids": [policy["id"]],
                "max_keys_per_user": 5,
            },
        ).json()

        # Accept v1 and create a key
        _accept_all_policies(client, profile["id"])
        key1 = client.post(
            "/api/keys",
            json={"name": "pre-reaccept-key", "profile_id": profile["id"]},
        ).json()
        assert key1["id"] is not None

        # Update policy (triggers reacceptance invalidation)
        client.put(
            f"/admin/api/policies/{policy['id']}",
            json={"content": "Version 2."},
        )

        # New key creation should fail
        response = client.post(
            "/api/keys",
            json={"name": "post-reaccept-key", "profile_id": profile["id"]},
        )
        assert response.status_code == 400

        # Reaccept and it should work again
        _accept_all_policies(client, profile["id"])
        response = client.post(
            "/api/keys",
            json={"name": "after-reaccept-key", "profile_id": profile["id"]},
        )
        assert response.status_code == 201

        # Cleanup
        client.post(f"/api/keys/{key1['id']}/revoke")
        client.post(f"/api/keys/{response.json()['id']}/revoke")
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")
