"""API key policy snapshot tests."""

from .conftest import accept_all_policies, create_test_profile_with_policy, cleanup_test_resources


class TestApiKeyPolicySnapshots:
    """Verify policy version snapshots on API keys."""

    def test_key_has_policy_snapshots(self, client):
        policy, profile = create_test_profile_with_policy(client, "snapshot")
        create = client.post("/api/keys", json={"name": "snapshot-test", "profile_id": profile["id"]}).json()
        assert len(create["policy_snapshot_ids"]) > 0
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_key_policy_snapshots_endpoint(self, client):
        policy, profile = create_test_profile_with_policy(client, "snap-ep")
        create = client.post("/api/keys", json={"name": "snap-ep-test", "profile_id": profile["id"]}).json()
        response = client.get(f"/api/keys/{create['id']}/policies")
        assert response.status_code == 200
        snapshots = response.json()
        assert isinstance(snapshots, list)
        assert len(snapshots) > 0
        assert "policy_name" in snapshots[0]
        assert "version_number" in snapshots[0]
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_admin_key_policy_snapshots(self, client):
        policy, profile = create_test_profile_with_policy(client, "admin-snap")
        create = client.post("/api/keys", json={"name": "admin-snap-test", "profile_id": profile["id"]}).json()
        response = client.get(f"/admin/api/keys/{create['id']}/policies")
        assert response.status_code == 200
        snapshots = response.json()
        assert len(snapshots) > 0
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_policy_snapshot_records_correct_version(self, client):
        policy = client.post("/admin/api/policies", json={"name": "key-test-policy-snap-version", "content": "Version 1."}).json()
        profile = client.post("/admin/api/profiles", json={"name": "key-test-profile-snap-version", "policy_ids": [policy["id"]]}).json()
        accept_all_policies(client, profile["id"])
        create = client.post("/api/keys", json={"name": "snap-version-test", "profile_id": profile["id"]}).json()
        client.put(f"/admin/api/policies/{policy['id']}", json={"content": "Version 2."})
        snapshots = client.get(f"/api/keys/{create['id']}/policies").json()
        assert len(snapshots) == 1
        assert snapshots[0]["version_number"] == 1
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])
