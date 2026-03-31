"""API key edit tests."""

from .conftest import create_test_profile_with_policy, cleanup_test_resources


class TestApiKeyEdit:
    """Verify API key editing."""

    def test_edit_vscode_continue(self, client):
        policy, profile = create_test_profile_with_policy(client, "edit-vscode")
        create = client.post("/api/keys", json={"name": "edit-vscode-test", "profile_id": profile["id"]}).json()
        assert create["vscode_continue"] is False
        response = client.put(f"/api/keys/{create['id']}", json={"vscode_continue": True})
        assert response.status_code == 200
        assert response.json()["vscode_continue"] is True
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_edit_not_found(self, client):
        response = client.put("/api/keys/99999", json={"vscode_continue": True})
        assert response.status_code == 404


class TestApiKeyEditEdgeCases:
    """Edge cases for API key editing."""

    def test_edit_toggle_vscode_on_and_off(self, client):
        policy, profile = create_test_profile_with_policy(client, "toggle-vsc")
        create = client.post("/api/keys", json={"name": "toggle-test", "profile_id": profile["id"]}).json()
        client.put(f"/api/keys/{create['id']}", json={"vscode_continue": True})
        resp = client.put(f"/api/keys/{create['id']}", json={"vscode_continue": False})
        assert resp.status_code == 200
        assert resp.json()["vscode_continue"] is False
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_edit_no_json_body(self, client):
        policy, profile = create_test_profile_with_policy(client, "edit-nobody")
        create = client.post("/api/keys", json={"name": "edit-nobody-test", "profile_id": profile["id"]}).json()
        response = client.put(f"/api/keys/{create['id']}")
        assert response.status_code == 400
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])

    def test_edit_does_not_change_name(self, client):
        policy, profile = create_test_profile_with_policy(client, "edit-noname")
        create = client.post("/api/keys", json={"name": "original-name", "profile_id": profile["id"]}).json()
        client.put(f"/api/keys/{create['id']}", json={"name": "new-name"})
        detail = client.get(f"/api/keys/{create['id']}").json()
        assert detail["name"] == "original-name"
        cleanup_test_resources(client, profile["id"], policy["id"], [create["id"]])
