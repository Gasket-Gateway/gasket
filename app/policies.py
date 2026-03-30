"""Policy data access — CRUD operations, versioning, acceptance, and config seeding.

All functions operate within a Flask application context and use
the SQLAlchemy session from app.models.db.
"""

import logging

from .models import (
    db,
    BackendProfile,
    Policy,
    PolicyAcceptance,
    PolicyVersion,
)

logger = logging.getLogger(__name__)


# ─── Read ──────────────────────────────────────────────────────────


def list_policies():
    """Return all policies, ordered by name."""
    return Policy.query.order_by(Policy.name).all()


def get_policy(policy_id):
    """Return a single policy by ID, or None."""
    return db.session.get(Policy, policy_id)


def get_policy_by_name(name):
    """Return a single policy by name, or None."""
    return Policy.query.filter_by(name=name).first()


def get_policy_versions(policy_id):
    """Return all versions for a policy, ordered by version_number."""
    return (
        PolicyVersion.query
        .filter_by(policy_id=policy_id)
        .order_by(PolicyVersion.version_number)
        .all()
    )


# ─── Create ────────────────────────────────────────────────────────


def create_policy(data):
    """Create a new policy with its initial version.

    Args:
        data: dict with policy fields. Required: name, content.
              Optional: description, enforce_reacceptance.

    Returns:
        The created Policy instance.

    Raises:
        ValueError: If name or content is missing, or name already exists.
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Policy name is required")

    content = (data.get("content") or "").strip()
    if not content:
        raise ValueError("Policy content is required")

    if get_policy_by_name(name):
        raise ValueError(f"Policy with name '{name}' already exists")

    policy = Policy(
        name=name,
        description=data.get("description", ""),
        enforce_reacceptance=data.get("enforce_reacceptance", False),
    )

    # Create initial version
    version = PolicyVersion(
        content=content,
        version_number=1,
    )
    policy.versions.append(version)

    db.session.add(policy)
    db.session.commit()
    return policy


# ─── Update ────────────────────────────────────────────────────────


def update_policy(policy_id, data):
    """Update an existing policy.

    If content is provided and differs from the current version,
    a new PolicyVersion is created. If enforce_reacceptance is enabled
    and content changed, existing acceptances for this policy are deleted.

    Args:
        policy_id: ID of the policy to update.
        data: dict of fields to update.

    Returns:
        The updated Policy instance.

    Raises:
        ValueError: If the policy doesn't exist or name conflicts.
    """
    policy = get_policy(policy_id)
    if not policy:
        raise ValueError(f"Policy {policy_id} not found")

    # Check name uniqueness if changed
    if "name" in data:
        new_name = (data["name"] or "").strip()
        if not new_name:
            raise ValueError("Policy name is required")
        existing = get_policy_by_name(new_name)
        if existing and existing.id != policy_id:
            raise ValueError(f"Policy with name '{new_name}' already exists")
        policy.name = new_name

    if "description" in data:
        policy.description = data["description"]

    if "enforce_reacceptance" in data:
        policy.enforce_reacceptance = data["enforce_reacceptance"]

    # Handle content update — create new version if changed
    content_changed = False
    if "content" in data:
        new_content = (data["content"] or "").strip()
        if not new_content:
            raise ValueError("Policy content is required")

        current = policy.current_version()
        if not current or current.content != new_content:
            next_version = (current.version_number + 1) if current else 1
            version = PolicyVersion(
                content=new_content,
                version_number=next_version,
            )
            policy.versions.append(version)
            content_changed = True

    # If content changed and reacceptance is enforced, invalidate acceptances
    if content_changed and policy.enforce_reacceptance:
        _invalidate_acceptances_for_policy(policy.id)

    db.session.commit()
    return policy


# ─── Delete ────────────────────────────────────────────────────────


def delete_policy(policy_id):
    """Delete a policy (cascades to versions and acceptances).

    Returns:
        True on success.

    Raises:
        ValueError: If the policy doesn't exist.
    """
    policy = get_policy(policy_id)
    if not policy:
        raise ValueError(f"Policy {policy_id} not found")

    db.session.delete(policy)
    db.session.commit()
    return True


# ─── Acceptance ────────────────────────────────────────────────────


def accept_policy(user_email, policy_id, profile_id):
    """Record a user's acceptance of a policy's current version for a profile.

    Args:
        user_email: The user's email address.
        policy_id: ID of the policy to accept.
        profile_id: ID of the backend profile this acceptance applies to.

    Returns:
        The created PolicyAcceptance instance.

    Raises:
        ValueError: If the policy, profile, or assignment doesn't exist,
                     or the policy has no versions.
    """
    policy = get_policy(policy_id)
    if not policy:
        raise ValueError(f"Policy {policy_id} not found")

    profile = db.session.get(BackendProfile, profile_id)
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")

    # Verify policy is assigned to profile
    if policy not in profile.policies:
        raise ValueError(f"Policy '{policy.name}' is not assigned to profile '{profile.name}'")

    current = policy.current_version()
    if not current:
        raise ValueError(f"Policy '{policy.name}' has no versions")

    # Remove any existing acceptance for this user/policy/profile combination
    PolicyAcceptance.query.filter_by(
        user_email=user_email,
        profile_id=profile_id,
        policy_version_id=current.id,
    ).delete()

    # Also clean up old version acceptances for same policy/profile
    old_version_ids = [v.id for v in policy.versions]
    PolicyAcceptance.query.filter(
        PolicyAcceptance.user_email == user_email,
        PolicyAcceptance.profile_id == profile_id,
        PolicyAcceptance.policy_version_id.in_(old_version_ids),
    ).delete()

    acceptance = PolicyAcceptance(
        user_email=user_email,
        policy_version_id=current.id,
        profile_id=profile_id,
    )
    db.session.add(acceptance)
    db.session.commit()
    return acceptance


def get_user_acceptances(user_email, profile_id=None):
    """Return all acceptance records for a user, optionally filtered by profile."""
    query = PolicyAcceptance.query.filter_by(user_email=user_email)
    if profile_id is not None:
        query = query.filter_by(profile_id=profile_id)
    return query.order_by(PolicyAcceptance.accepted_at.desc()).all()


def get_all_acceptances(user_email=None):
    """Return all acceptance records, optionally filtered by user."""
    query = PolicyAcceptance.query
    if user_email:
        query = query.filter_by(user_email=user_email)
    return query.order_by(PolicyAcceptance.accepted_at.desc()).all()


def check_all_policies_accepted(user_email, profile_id):
    """Check if a user has accepted the current version of all policies for a profile.

    Returns:
        dict with 'all_accepted' (bool), 'accepted' (list), 'pending' (list).
    """
    profile = db.session.get(BackendProfile, profile_id)
    if not profile:
        return {"all_accepted": False, "accepted": [], "pending": []}

    accepted = []
    pending = []

    for policy in profile.policies:
        current = policy.current_version()
        if not current:
            pending.append({"policy_id": policy.id, "policy_name": policy.name})
            continue

        # Check if user has accepted the current version for this profile
        acceptance = PolicyAcceptance.query.filter_by(
            user_email=user_email,
            policy_version_id=current.id,
            profile_id=profile_id,
        ).first()

        if acceptance:
            accepted.append({
                "policy_id": policy.id,
                "policy_name": policy.name,
                "version_number": current.version_number,
                "accepted_at": acceptance.accepted_at.isoformat() if acceptance.accepted_at else None,
            })
        else:
            pending.append({
                "policy_id": policy.id,
                "policy_name": policy.name,
                "current_version": current.version_number,
            })

    return {
        "all_accepted": len(pending) == 0,
        "accepted": accepted,
        "pending": pending,
    }


# ─── Helpers ───────────────────────────────────────────────────────


def _invalidate_acceptances_for_policy(policy_id):
    """Delete all acceptances linked to any version of a policy."""
    version_ids = [
        v.id for v in PolicyVersion.query.filter_by(policy_id=policy_id).all()
    ]
    if version_ids:
        PolicyAcceptance.query.filter(
            PolicyAcceptance.policy_version_id.in_(version_ids)
        ).delete()


# ─── Config seeding ───────────────────────────────────────────────


def seed_config_policies(app):
    """Sync config-defined policies into the database.

    - Upserts policies listed in config.yaml under policies
    - Creates new versions when content changes
    - Config policies always have enforce_reacceptance=False
    - Removes config-sourced DB rows whose names are no longer in config
    - Admin-created policies are never touched

    Must be called within a Flask application context.
    """
    config = app.config["GASKET"]
    config_policies = config.get("policies", [])
    config_names = {p.get("name") for p in config_policies if p.get("name")}

    with app.app_context():
        for entry in config_policies:
            name = entry.get("name")
            if not name:
                logger.warning("Skipping config policy with no name: %s", entry)
                continue

            content = entry.get("content", "")
            if not content:
                logger.warning("Skipping config policy '%s' with no content", name)
                continue

            existing = get_policy_by_name(name)

            if existing:
                if existing.source == "config":
                    # Update config-sourced policy
                    existing.description = entry.get("description", existing.description)
                    existing.enforce_reacceptance = False  # Always disabled for config

                    # Check if content changed — create new version if so
                    current = existing.current_version()
                    if not current or current.content != content:
                        next_version = (current.version_number + 1) if current else 1
                        version = PolicyVersion(
                            content=content,
                            version_number=next_version,
                        )
                        existing.versions.append(version)
                        logger.info("New version for config policy: %s (v%d)", name, next_version)

                    logger.info("Updated config policy: %s", name)
                else:
                    logger.warning(
                        "Config policy '%s' conflicts with admin-created policy — skipping",
                        name,
                    )
            else:
                policy = Policy(
                    name=name,
                    description=entry.get("description", ""),
                    source="config",
                    enforce_reacceptance=False,
                )
                version = PolicyVersion(
                    content=content,
                    version_number=1,
                )
                policy.versions.append(version)
                db.session.add(policy)
                logger.info("Seeded config policy: %s", name)

        # Remove stale config-sourced policies
        stale = Policy.query.filter(
            Policy.source == "config",
            ~Policy.name.in_(config_names) if config_names else True,
        ).all()
        for policy in stale:
            logger.info("Removing stale config policy: %s", policy.name)
            db.session.delete(policy)

        db.session.commit()
