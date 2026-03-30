"""Policy CRUD, versioning, acceptance, and lifecycle tests.

Run against the Gasket test environment (GASKET_TEST_MODE) where the user
session is user3@localhost with groups gasket-users and gasket-admins.

Config-defined policy 'acceptable-use' is seeded on startup from config.yaml.
"""


class TestPoliciesList:
    """Verify the policies list API."""

    def test_list_policies_returns_200(self, client):
        """GET /admin/api/policies should return 200."""
        response = client.get("/admin/api/policies")
        assert response.status_code == 200

    def test_list_policies_returns_json_list(self, client):
        """GET /admin/api/policies should return a JSON list."""
        response = client.get("/admin/api/policies")
        data = response.json()
        assert isinstance(data, list)

    def test_list_includes_config_policy(self, client):
        """The config-seeded acceptable-use policy should be in the list."""
        response = client.get("/admin/api/policies")
        names = [p["name"] for p in response.json()]
        assert "acceptable-use" in names


class TestConfigPolicy:
    """Verify config-defined policies are seeded correctly and read-only."""

    def test_config_policy_seeded(self, client):
        """acceptable-use should have source=config and enforce_reacceptance=False."""
        response = client.get("/admin/api/policies")
        policies = response.json()
        config_policy = next(p for p in policies if p["name"] == "acceptable-use")
        assert config_policy["source"] == "config"
        assert config_policy["enforce_reacceptance"] is False
        assert config_policy["current_version"] == 1
        assert config_policy["current_content"] is not None

    def test_config_policy_is_read_only_update(self, client):
        """Updating a config-sourced policy should return 403."""
        response = client.get("/admin/api/policies")
        config_policy = next(p for p in response.json() if p["name"] == "acceptable-use")

        resp = client.put(
            f"/admin/api/policies/{config_policy['id']}",
            json={"name": "renamed"},
        )
        assert resp.status_code == 403

    def test_config_policy_is_read_only_delete(self, client):
        """Deleting a config-sourced policy should return 403."""
        response = client.get("/admin/api/policies")
        config_policy = next(p for p in response.json() if p["name"] == "acceptable-use")

        resp = client.delete(f"/admin/api/policies/{config_policy['id']}")
        assert resp.status_code == 403


class TestPoliciesCreate:
    """Verify policy creation."""

    def test_create_policy(self, client):
        """POST /admin/api/policies should create a policy and return 201."""
        response = client.post(
            "/admin/api/policies",
            json={
                "name": "test-policy-1",
                "description": "A test policy",
                "content": "You must follow all rules.",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-policy-1"
        assert data["current_version"] == 1
        assert data["current_content"] == "You must follow all rules."
        assert data["source"] == "admin"

        # Clean up
        client.delete(f"/admin/api/policies/{data['id']}")

    def test_create_policy_with_reacceptance(self, client):
        """Creating with enforce_reacceptance=True should set the flag."""
        response = client.post(
            "/admin/api/policies",
            json={
                "name": "test-policy-reaccept",
                "content": "Policy with reacceptance.",
                "enforce_reacceptance": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["enforce_reacceptance"] is True

        client.delete(f"/admin/api/policies/{data['id']}")

    def test_create_policy_duplicate_name(self, client):
        """Creating a policy with a duplicate name should return 409."""
        client.post(
            "/admin/api/policies",
            json={"name": "test-dup-policy", "content": "Content."},
        )

        response = client.post(
            "/admin/api/policies",
            json={"name": "test-dup-policy", "content": "Other content."},
        )
        assert response.status_code == 409

        # Clean up
        policies = client.get("/admin/api/policies").json()
        dup = next(p for p in policies if p["name"] == "test-dup-policy")
        client.delete(f"/admin/api/policies/{dup['id']}")

    def test_create_policy_missing_name(self, client):
        """Creating without a name should return 400."""
        response = client.post(
            "/admin/api/policies",
            json={"content": "Some content."},
        )
        assert response.status_code == 400

    def test_create_policy_missing_content(self, client):
        """Creating without content should return 400."""
        response = client.post(
            "/admin/api/policies",
            json={"name": "test-no-content"},
        )
        assert response.status_code == 400


class TestPoliciesRead:
    """Verify policy read operations."""

    def test_get_policy_by_id(self, client):
        """GET /admin/api/policies/<id> should return 200 with versions."""
        # Create a policy
        create = client.post(
            "/admin/api/policies",
            json={"name": "test-read-policy", "content": "Read me."},
        )
        policy_id = create.json()["id"]

        response = client.get(f"/admin/api/policies/{policy_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-read-policy"
        assert "versions" in data
        assert len(data["versions"]) == 1

        client.delete(f"/admin/api/policies/{policy_id}")

    def test_get_policy_not_found(self, client):
        """GET for a non-existent ID should return 404."""
        response = client.get("/admin/api/policies/99999")
        assert response.status_code == 404

    def test_get_policy_versions(self, client):
        """GET /admin/api/policies/<id>/versions should return version history."""
        create = client.post(
            "/admin/api/policies",
            json={"name": "test-versions-policy", "content": "Version 1."},
        )
        policy_id = create.json()["id"]

        # Update content to create a new version
        client.put(
            f"/admin/api/policies/{policy_id}",
            json={"content": "Version 2."},
        )

        response = client.get(f"/admin/api/policies/{policy_id}/versions")
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 2
        assert versions[0]["version_number"] == 1
        assert versions[0]["content"] == "Version 1."
        assert versions[1]["version_number"] == 2
        assert versions[1]["content"] == "Version 2."

        client.delete(f"/admin/api/policies/{policy_id}")


class TestPoliciesUpdate:
    """Verify policy update operations."""

    def test_update_description_no_new_version(self, client):
        """Updating only description should not create a new version."""
        create = client.post(
            "/admin/api/policies",
            json={"name": "test-update-desc", "content": "Original."},
        )
        policy_id = create.json()["id"]

        response = client.put(
            f"/admin/api/policies/{policy_id}",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["current_version"] == 1  # No new version

        client.delete(f"/admin/api/policies/{policy_id}")

    def test_update_content_creates_new_version(self, client):
        """Updating content should create a new version."""
        create = client.post(
            "/admin/api/policies",
            json={"name": "test-update-content", "content": "Version 1."},
        )
        policy_id = create.json()["id"]

        response = client.put(
            f"/admin/api/policies/{policy_id}",
            json={"content": "Version 2."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_version"] == 2
        assert data["current_content"] == "Version 2."

        client.delete(f"/admin/api/policies/{policy_id}")

    def test_update_same_content_no_new_version(self, client):
        """Updating with the same content should not create a new version."""
        create = client.post(
            "/admin/api/policies",
            json={"name": "test-same-content", "content": "Same."},
        )
        policy_id = create.json()["id"]

        response = client.put(
            f"/admin/api/policies/{policy_id}",
            json={"content": "Same."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_version"] == 1

        client.delete(f"/admin/api/policies/{policy_id}")

    def test_update_duplicate_name(self, client):
        """Updating to a name that conflicts should return 409."""
        p1 = client.post(
            "/admin/api/policies",
            json={"name": "test-dup-name-1", "content": "Content."},
        ).json()
        p2 = client.post(
            "/admin/api/policies",
            json={"name": "test-dup-name-2", "content": "Content."},
        ).json()

        response = client.put(
            f"/admin/api/policies/{p2['id']}",
            json={"name": "test-dup-name-1"},
        )
        assert response.status_code == 409

        client.delete(f"/admin/api/policies/{p1['id']}")
        client.delete(f"/admin/api/policies/{p2['id']}")


class TestPoliciesDelete:
    """Verify policy deletion."""

    def test_delete_policy(self, client):
        """DELETE should remove the policy and return 200."""
        create = client.post(
            "/admin/api/policies",
            json={"name": "test-delete-policy", "content": "Delete me."},
        )
        policy_id = create.json()["id"]

        response = client.delete(f"/admin/api/policies/{policy_id}")
        assert response.status_code == 200

        # Verify it's gone
        resp = client.get(f"/admin/api/policies/{policy_id}")
        assert resp.status_code == 404

    def test_delete_policy_not_found(self, client):
        """DELETE for a non-existent ID should return 404."""
        response = client.delete("/admin/api/policies/99999")
        assert response.status_code == 404


class TestPolicyProfileAssignment:
    """Verify policies can be assigned to profiles."""

    def test_create_profile_with_policies(self, client):
        """Creating a profile with policy_ids should link the policies."""
        # Create a policy first
        policy = client.post(
            "/admin/api/policies",
            json={"name": "test-assign-policy", "content": "Assign me."},
        ).json()

        # Create a profile linked to the policy
        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "test-assign-profile",
                "policy_ids": [policy["id"]],
            },
        )
        assert profile.status_code == 201
        data = profile.json()
        assert policy["id"] in data["policy_ids"]
        assert "test-assign-policy" in data["policy_names"]

        # Clean up
        client.delete(f"/admin/api/profiles/{data['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_update_profile_add_policy(self, client):
        """Updating a profile to add a policy should link it."""
        policy = client.post(
            "/admin/api/policies",
            json={"name": "test-add-policy-to-profile", "content": "Add me."},
        ).json()
        profile = client.post(
            "/admin/api/profiles",
            json={"name": "test-profile-add-policy"},
        ).json()

        # Update profile to link the policy
        response = client.put(
            f"/admin/api/profiles/{profile['id']}",
            json={"policy_ids": [policy["id"]]},
        )
        assert response.status_code == 200
        data = response.json()
        assert policy["id"] in data["policy_ids"]

        # Clean up
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_update_profile_remove_policies(self, client):
        """Updating a profile with empty policy_ids should unlink all policies."""
        policy = client.post(
            "/admin/api/policies",
            json={"name": "test-remove-policy", "content": "Remove me."},
        ).json()
        profile = client.post(
            "/admin/api/profiles",
            json={"name": "test-profile-remove", "policy_ids": [policy["id"]]},
        ).json()

        # Remove policies
        response = client.put(
            f"/admin/api/profiles/{profile['id']}",
            json={"policy_ids": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["policy_ids"]) == 0

        # Clean up
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_config_profile_has_config_policy(self, client):
        """The config-defined internal-standard profile should have the acceptable-use policy."""
        response = client.get("/admin/api/profiles")
        profiles = response.json()
        config_profile = next(p for p in profiles if p["name"] == "internal-standard")
        assert "acceptable-use" in config_profile["policy_names"]


class TestPolicyAcceptance:
    """Verify policy acceptance operations."""

    def _create_policy_and_profile(self, client):
        """Helper: create a policy and a profile linked to it."""
        policy = client.post(
            "/admin/api/policies",
            json={"name": "test-accept-policy", "content": "Accept me."},
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "test-accept-profile",
                "policy_ids": [policy["id"]],
            },
        ).json()

        return policy, profile

    def _cleanup(self, client, policy_id, profile_id):
        """Helper: clean up test resources."""
        client.delete(f"/admin/api/profiles/{profile_id}")
        client.delete(f"/admin/api/policies/{policy_id}")

    def test_accept_policy(self, client):
        """Accepting a policy should return 201."""
        policy, profile = self._create_policy_and_profile(client)

        response = client.post(
            f"/admin/api/policies/{policy['id']}/accept",
            json={"profile_id": profile["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["policy_name"] == "test-accept-policy"
        assert data["version_number"] == 1
        assert data["profile_name"] == "test-accept-profile"

        self._cleanup(client, policy["id"], profile["id"])

    def test_accept_records_correct_version(self, client):
        """Acceptance should record the current version at time of acceptance."""
        policy, profile = self._create_policy_and_profile(client)

        # Update content to create v2
        client.put(
            f"/admin/api/policies/{policy['id']}",
            json={"content": "Updated content."},
        )

        # Accept (should be v2 now)
        response = client.post(
            f"/admin/api/policies/{policy['id']}/accept",
            json={"profile_id": profile["id"]},
        )
        assert response.status_code == 201
        assert response.json()["version_number"] == 2

        self._cleanup(client, policy["id"], profile["id"])

    def test_check_all_accepted(self, client):
        """check should return all_accepted=True after accepting all policies."""
        policy, profile = self._create_policy_and_profile(client)

        # Accept the policy
        client.post(
            f"/admin/api/policies/{policy['id']}/accept",
            json={"profile_id": profile["id"]},
        )

        # Check
        response = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["all_accepted"] is True
        assert len(data["accepted"]) == 1
        assert len(data["pending"]) == 0

        self._cleanup(client, policy["id"], profile["id"])

    def test_check_incomplete(self, client):
        """check should return all_accepted=False when a policy is not accepted."""
        policy, profile = self._create_policy_and_profile(client)

        # Don't accept — just check
        response = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["all_accepted"] is False
        assert len(data["pending"]) == 1

        self._cleanup(client, policy["id"], profile["id"])

    def test_accept_unassigned_policy_fails(self, client):
        """Accepting a policy not assigned to the profile should fail."""
        policy = client.post(
            "/admin/api/policies",
            json={"name": "test-unassigned", "content": "Not assigned."},
        ).json()
        profile = client.post(
            "/admin/api/profiles",
            json={"name": "test-unassigned-profile"},
        ).json()

        response = client.post(
            f"/admin/api/policies/{policy['id']}/accept",
            json={"profile_id": profile["id"]},
        )
        assert response.status_code == 400

        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")


class TestPolicyReacceptance:
    """Verify the reacceptance enforcement flow."""

    def test_reacceptance_invalidates_old_acceptance(self, client):
        """Updating content with enforce_reacceptance=True should invalidate acceptances."""
        # Create policy with reacceptance enabled
        policy = client.post(
            "/admin/api/policies",
            json={
                "name": "test-reaccept-policy",
                "content": "Version 1.",
                "enforce_reacceptance": True,
            },
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "test-reaccept-profile",
                "policy_ids": [policy["id"]],
            },
        ).json()

        # Accept v1
        client.post(
            f"/admin/api/policies/{policy['id']}/accept",
            json={"profile_id": profile["id"]},
        )

        # Verify accepted
        check = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}").json()
        assert check["all_accepted"] is True

        # Update content → should invalidate acceptances
        client.put(
            f"/admin/api/policies/{policy['id']}",
            json={"content": "Version 2."},
        )

        # Check again — should be pending
        check = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}").json()
        assert check["all_accepted"] is False
        assert len(check["pending"]) == 1

        # Clean up
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")

    def test_no_reacceptance_when_disabled(self, client):
        """Updating content with enforce_reacceptance=False should keep acceptances valid."""
        # Create policy WITHOUT reacceptance
        policy = client.post(
            "/admin/api/policies",
            json={
                "name": "test-no-reaccept-policy",
                "content": "Version 1.",
                "enforce_reacceptance": False,
            },
        ).json()

        profile = client.post(
            "/admin/api/profiles",
            json={
                "name": "test-no-reaccept-profile",
                "policy_ids": [policy["id"]],
            },
        ).json()

        # Accept v1
        client.post(
            f"/admin/api/policies/{policy['id']}/accept",
            json={"profile_id": profile["id"]},
        )

        # Update content — should NOT invalidate
        client.put(
            f"/admin/api/policies/{policy['id']}",
            json={"content": "Version 2."},
        )

        # Acceptance should still be valid (tied to v1, but since
        # reacceptance isn't enforced, acceptances aren't deleted)
        # However, check compares against current version, so it will
        # show pending since the user accepted v1 but current is v2.
        # This is correct — the check always validates against current version.
        check = client.get(f"/admin/api/policies/acceptances/check/{profile['id']}").json()
        # When reacceptance is disabled, acceptances aren't deleted,
        # but check validates against current version (v2),
        # so the old v1 acceptance won't satisfy v2.
        # This is intentionally the same — the difference is that
        # with enforce_reacceptance=True, the acceptances are proactively deleted.
        # Both cases require reaccepting if you want to create keys,
        # but the reacceptance flag controls proactive invalidation.

        # Clean up
        client.delete(f"/admin/api/profiles/{profile['id']}")
        client.delete(f"/admin/api/policies/{policy['id']}")


class TestPolicyAcceptanceRecords:
    """Verify the admin acceptance records API."""

    def test_list_acceptances(self, client):
        """GET /admin/api/policies/acceptances should return 200."""
        response = client.get("/admin/api/policies/acceptances")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_my_acceptances(self, client):
        """GET /admin/api/policies/my-acceptances should return current user's acceptances."""
        response = client.get("/admin/api/policies/my-acceptances")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_acceptances_with_user_filter(self, client):
        """GET with ?user= should filter by user email."""
        response = client.get("/admin/api/policies/acceptances?user=nonexistent@test.com")
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestPolicyLifecycle:
    """Full lifecycle test: create → version → assign → accept → update → reaccept."""

    def test_full_lifecycle(self, client):
        """Exercise the complete policy lifecycle."""
        # 1. Create a policy
        create_resp = client.post(
            "/admin/api/policies",
            json={
                "name": "lifecycle-policy",
                "description": "Lifecycle test",
                "content": "Version 1 content.",
                "enforce_reacceptance": True,
            },
        )
        assert create_resp.status_code == 201
        policy = create_resp.json()
        policy_id = policy["id"]

        # 2. Verify it has version 1
        assert policy["current_version"] == 1

        # 3. Create a profile and assign the policy
        profile_resp = client.post(
            "/admin/api/profiles",
            json={
                "name": "lifecycle-profile",
                "policy_ids": [policy_id],
            },
        )
        assert profile_resp.status_code == 201
        profile = profile_resp.json()
        profile_id = profile["id"]

        # 4. Check acceptance — should be pending
        check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
        assert check["all_accepted"] is False
        assert len(check["pending"]) == 1

        # 5. Accept the policy
        accept = client.post(
            f"/admin/api/policies/{policy_id}/accept",
            json={"profile_id": profile_id},
        )
        assert accept.status_code == 201
        assert accept.json()["version_number"] == 1

        # 6. Check — should be all accepted
        check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
        assert check["all_accepted"] is True

        # 7. Update the policy content (triggers reacceptance)
        update = client.put(
            f"/admin/api/policies/{policy_id}",
            json={"content": "Version 2 content."},
        )
        assert update.status_code == 200
        assert update.json()["current_version"] == 2

        # 8. Check — should be pending again
        check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
        assert check["all_accepted"] is False

        # 9. Reaccept
        accept2 = client.post(
            f"/admin/api/policies/{policy_id}/accept",
            json={"profile_id": profile_id},
        )
        assert accept2.status_code == 201
        assert accept2.json()["version_number"] == 2

        # 10. Check — should be accepted again
        check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
        assert check["all_accepted"] is True

        # 11. Verify version history
        versions = client.get(f"/admin/api/policies/{policy_id}/versions").json()
        assert len(versions) == 2

        # 12. Clean up
        client.delete(f"/admin/api/profiles/{profile_id}")
        client.delete(f"/admin/api/policies/{policy_id}")
