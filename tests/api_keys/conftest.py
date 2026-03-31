"""Shared helpers for API key tests."""

import pytest


def accept_all_policies(client, profile_id):
    """Accept all pending policies for a profile as the test user."""
    check = client.get(f"/admin/api/policies/acceptances/check/{profile_id}").json()
    for pending in check.get("pending", []):
        client.post(
            f"/admin/api/policies/{pending['policy_id']}/accept",
            json={"profile_id": profile_id},
        )


def create_test_profile_with_policy(client, name_suffix="1"):
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

    accept_all_policies(client, profile["id"])
    return policy, profile


def cleanup_test_resources(client, profile_id, policy_id, key_ids=None):
    """Clean up test resources."""
    if key_ids:
        for key_id in key_ids:
            client.post(f"/api/keys/{key_id}/revoke")
    if profile_id:
        client.delete(f"/admin/api/profiles/{profile_id}")
    if policy_id:
        client.delete(f"/admin/api/policies/{policy_id}")
