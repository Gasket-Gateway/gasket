"""Backend profiles CRUD tests — run against the Gasket test environment (GASKET_TEST_MODE).

Tests cover the full lifecycle of backend profiles including:
  - List, create, read, update, delete operations
  - Multiple OIDC groups support
  - Backend association with validation
  - Name uniqueness enforcement
  - Admin page integration
"""


class TestProfilesList:
    """Verify the profiles list API."""

    def test_list_profiles_returns_200(self, client):
        """GET /admin/api/profiles should return 200."""
        response = client.get("/admin/api/profiles")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestProfilesCreate:
    """Verify profile creation."""

    def test_create_profile(self, client):
        """POST /admin/api/profiles should create a profile and return 201."""
        response = client.post(
            "/admin/api/profiles",
            json={
                "name": "test-profile-1",
                "oidc_groups": ["gasket-users", "gasket-admins"],
                "description": "Standard access\nWith multi-line support",
                "policy_text": "Do not abuse\nBe responsible",
                "metadata_audit": True,
                "content_audit": False,
                "max_keys_per_user": 3,
                "default_expiry_days": 30,
                "enforce_expiry": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-profile-1"
        assert data["oidc_groups"] == ["gasket-users", "gasket-admins"]
        assert data["default_expiry_days"] == 30
        assert data["max_keys_per_user"] == 3
        assert "\n" in data["description"]

        # Clean up
        client.delete(f"/admin/api/profiles/{data['id']}")

    def test_create_profile_single_group(self, client):
        """A single OIDC group should be returned as a one-element list."""
        response = client.post(
            "/admin/api/profiles",
            json={"name": "test-single-group", "oidc_groups": ["gasket-users"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["oidc_groups"] == ["gasket-users"]

        client.delete(f"/admin/api/profiles/{data['id']}")

    def test_create_profile_no_groups(self, client):
        """No OIDC groups should return an empty list."""
        response = client.post(
            "/admin/api/profiles",
            json={"name": "test-no-groups"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["oidc_groups"] == []

        client.delete(f"/admin/api/profiles/{data['id']}")

    def test_create_profile_duplicate_name(self, client):
        """Duplicate profile name should return 409."""
        payload = {"name": "test-duplicate-profile"}
        resp1 = client.post("/admin/api/profiles", json=payload)
        assert resp1.status_code == 201
        profile_id = resp1.json()["id"]

        resp2 = client.post("/admin/api/profiles", json=payload)
        assert resp2.status_code == 409

        client.delete(f"/admin/api/profiles/{profile_id}")

    def test_create_profile_missing_name(self, client):
        """Missing name should return 400."""
        response = client.post("/admin/api/profiles", json={"description": "No name"})
        assert response.status_code == 400

    def test_create_profile_with_backends(self, client):
        """Creating a profile with associated backends."""
        # Setup: Ensure a backend exists to link to
        backend_resp = client.post("/admin/api/backends", json={
            "name": "test-assoc-backend",
            "base_url": "http://dummy",
        })
        assert backend_resp.status_code == 201
        backend_id = backend_resp.json()["id"]

        # Create Profile
        profile_resp = client.post("/admin/api/profiles", json={
            "name": "test-profile-with-backends",
            "backend_ids": [backend_id]
        })
        assert profile_resp.status_code == 201
        data = profile_resp.json()
        assert backend_id in data["backend_ids"]
        assert "test-assoc-backend" in data["backend_names"]

        # Clean up
        client.delete(f"/admin/api/profiles/{data['id']}")
        client.delete(f"/admin/api/backends/{backend_id}")

    def test_create_profile_invalid_backend(self, client):
        """Creating a profile with an invalid backend ID should return 400."""
        profile_resp = client.post("/admin/api/profiles", json={
            "name": "test-profile-invalid-backend",
            "backend_ids": [99999]
        })
        assert profile_resp.status_code == 400

    def test_create_profile_empty_body(self, client):
        """Empty request body should return 400."""
        response = client.post(
            "/admin/api/profiles",
            data="not json",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 400


class TestProfilesRead:
    """Verify reading individual profiles."""

    def test_get_profile(self, client):
        """GET /admin/api/profiles/<id> should return the profile."""
        create_resp = client.post(
            "/admin/api/profiles",
            json={"name": "test-get-profile"},
        )
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]

        response = client.get(f"/admin/api/profiles/{profile_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-get-profile"
        # Verify response structure
        assert "oidc_groups" in data
        assert "backend_ids" in data
        assert "backend_names" in data
        assert "metadata_audit" in data
        assert "open_webui_enabled" in data

        client.delete(f"/admin/api/profiles/{profile_id}")

    def test_get_profile_not_found(self, client):
        """GET non-existent profile should return 404."""
        response = client.get("/admin/api/profiles/99999")
        assert response.status_code == 404


class TestProfilesUpdate:
    """Verify profile updates."""

    def test_update_profile(self, client):
        """PUT /admin/api/profiles/<id> should update the profile."""
        create_resp = client.post(
            "/admin/api/profiles",
            json={"name": "test-update-profile", "max_keys_per_user": 2},
        )
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]

        update_resp = client.put(
            f"/admin/api/profiles/{profile_id}",
            json={"name": "test-updated-name", "max_keys_per_user": 10},
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "test-updated-name"
        assert data["max_keys_per_user"] == 10

        client.delete(f"/admin/api/profiles/{profile_id}")

    def test_update_profile_oidc_groups(self, client):
        """Updating OIDC groups should replace the existing list."""
        create_resp = client.post(
            "/admin/api/profiles",
            json={"name": "test-update-groups", "oidc_groups": ["group-a"]},
        )
        profile_id = create_resp.json()["id"]

        update_resp = client.put(
            f"/admin/api/profiles/{profile_id}",
            json={"oidc_groups": ["group-b", "group-c"]},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["oidc_groups"] == ["group-b", "group-c"]

        client.delete(f"/admin/api/profiles/{profile_id}")

    def test_update_profile_backends(self, client):
        """Updating backend associations should work."""
        backend_resp = client.post("/admin/api/backends", json={
            "name": "test-update-assoc-backend",
            "base_url": "http://dummy",
        })
        backend_id = backend_resp.json()["id"]

        create_resp = client.post(
            "/admin/api/profiles",
            json={"name": "test-update-backends"},
        )
        profile_id = create_resp.json()["id"]

        # Add backend
        update_resp = client.put(
            f"/admin/api/profiles/{profile_id}",
            json={"backend_ids": [backend_id]},
        )
        assert update_resp.status_code == 200
        assert backend_id in update_resp.json()["backend_ids"]

        # Remove all backends
        update_resp2 = client.put(
            f"/admin/api/profiles/{profile_id}",
            json={"backend_ids": []},
        )
        assert update_resp2.status_code == 200
        assert update_resp2.json()["backend_ids"] == []

        client.delete(f"/admin/api/profiles/{profile_id}")
        client.delete(f"/admin/api/backends/{backend_id}")

    def test_update_profile_duplicate_name(self, client):
        """Updating to an existing profile name should return 409."""
        resp1 = client.post("/admin/api/profiles", json={"name": "p1"})
        p1_id = resp1.json()["id"]

        resp2 = client.post("/admin/api/profiles", json={"name": "p2"})
        p2_id = resp2.json()["id"]

        update_resp = client.put(f"/admin/api/profiles/{p2_id}", json={"name": "p1"})
        assert update_resp.status_code == 409

        client.delete(f"/admin/api/profiles/{p1_id}")
        client.delete(f"/admin/api/profiles/{p2_id}")

    def test_update_profile_not_found(self, client):
        """Updating a non-existent profile should return 404."""
        response = client.put(
            "/admin/api/profiles/99999",
            json={"name": "nope"},
        )
        assert response.status_code == 404


class TestProfilesDelete:
    """Verify profile deletion."""

    def test_delete_profile(self, client):
        """DELETE /admin/api/profiles/<id> should delete the profile."""
        create_resp = client.post(
            "/admin/api/profiles",
            json={"name": "test-delete-profile"},
        )
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/admin/api/profiles/{profile_id}")
        assert delete_resp.status_code == 200

        get_resp = client.get(f"/admin/api/profiles/{profile_id}")
        assert get_resp.status_code == 404

    def test_delete_profile_not_found(self, client):
        """Deleting a non-existent profile should return 404."""
        response = client.delete("/admin/api/profiles/99999")
        assert response.status_code == 404

    def test_delete_profile_preserves_backends(self, client):
        """Deleting a profile should not delete the linked backends."""
        backend_resp = client.post("/admin/api/backends", json={
            "name": "test-preserved-backend",
            "base_url": "http://dummy",
        })
        backend_id = backend_resp.json()["id"]

        create_resp = client.post("/admin/api/profiles", json={
            "name": "test-delete-preserves",
            "backend_ids": [backend_id],
        })
        profile_id = create_resp.json()["id"]

        # Delete profile
        client.delete(f"/admin/api/profiles/{profile_id}")

        # Backend should still exist
        backend_check = client.get(f"/admin/api/backends/{backend_id}")
        assert backend_check.status_code == 200

        # Clean up
        client.delete(f"/admin/api/backends/{backend_id}")


class TestProfilesLifecycle:
    """End-to-end lifecycle test."""

    def test_full_crud_lifecycle(self, client):
        """Full CRUD lifecycle for a backend profile."""
        # Create backend to associate
        backend_resp = client.post("/admin/api/backends", json={
            "name": "lifecycle-backend",
            "base_url": "http://dummy",
        })
        backend_id = backend_resp.json()["id"]

        # Create profile
        create_resp = client.post("/admin/api/profiles", json={
            "name": "lifecycle-profile",
            "description": "Test lifecycle",
            "oidc_groups": ["group-a", "group-b"],
            "backend_ids": [backend_id],
            "metadata_audit": True,
            "content_audit": True,
            "max_keys_per_user": 3,
            "default_expiry_days": 90,
            "enforce_expiry": True,
            "open_webui_enabled": True,
        })
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]

        # List should include it
        list_resp = client.get("/admin/api/profiles")
        profile_names = [p["name"] for p in list_resp.json()]
        assert "lifecycle-profile" in profile_names

        # Read
        get_resp = client.get(f"/admin/api/profiles/{profile_id}")
        data = get_resp.json()
        assert data["oidc_groups"] == ["group-a", "group-b"]
        assert data["content_audit"] is True
        assert data["open_webui_enabled"] is True
        assert data["default_expiry_days"] == 90

        # Update
        update_resp = client.put(f"/admin/api/profiles/{profile_id}", json={
            "name": "lifecycle-profile-v2",
            "oidc_groups": ["group-c"],
            "max_keys_per_user": 10,
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "lifecycle-profile-v2"
        assert update_resp.json()["oidc_groups"] == ["group-c"]

        # Delete
        delete_resp = client.delete(f"/admin/api/profiles/{profile_id}")
        assert delete_resp.status_code == 200

        # Verify profile gone, backend preserved
        assert client.get(f"/admin/api/profiles/{profile_id}").status_code == 404
        assert client.get(f"/admin/api/backends/{backend_id}").status_code == 200

        # Clean up backend
        client.delete(f"/admin/api/backends/{backend_id}")


class TestProfilesAdminPage:
    """Verify the admin page includes profiles content."""

    def test_admin_page_contains_profiles(self, client):
        """GET /admin should contain Backend Profiles section."""
        response = client.get("/admin")
        assert response.status_code == 200
        assert "Backend Profiles" in response.text
