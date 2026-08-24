"""Create the approved PostgreSQL extension baseline."""

from alembic import op

revision: str = "0000_extensions"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    # pgcrypto may be shared by provider-managed or later application objects.
    pass
