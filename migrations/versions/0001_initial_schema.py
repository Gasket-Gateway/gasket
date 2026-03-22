"""Initial database schema — creates the Gasket database structure.

Revision ID: 0001
Revises: -
Create Date: 2026-03-22
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial Gasket database schema."""
    # Placeholder — tables will be added here as features are implemented.
    # This migration establishes the alembic_version tracking table.
    pass


def downgrade() -> None:
    """Remove the initial Gasket database schema."""
    # Placeholder — DROP TABLE statements will be added as the upgrade is populated.
    pass
