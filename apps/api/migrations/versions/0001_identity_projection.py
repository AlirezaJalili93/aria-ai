"""Create Account, Profile, and Membership identity projection tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_identity_projection"
down_revision: str | None = "0000_extensions"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.String(length=50), server_default="free", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active','suspended','closed')", name="account_status"),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
    )
    op.create_table(
        "profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=True),
        sa.Column("locale", sa.String(length=20), server_default="fa-IR", nullable=False),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_profiles"),
    )
    op.create_table(
        "account_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('owner','admin','member')", name="membership_role"),
        sa.CheckConstraint(
            "status IN ('active','invited','suspended')",
            name="membership_status",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_account_memberships_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["profiles.user_id"], name="fk_account_memberships_user_id_profiles"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account_memberships"),
        sa.UniqueConstraint(
            "account_id", "user_id", name="uq_account_memberships_account_id_user_id"
        ),
    )
    op.create_index(
        "ix_account_memberships_user_id_status",
        "account_memberships",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_account_memberships_account_id_status",
        "account_memberships",
        ["account_id", "status"],
        unique=False,
    )
    op.execute("ALTER TABLE accounts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE account_memberships ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_account_memberships_account_id_status", table_name="account_memberships")
    op.drop_index("ix_account_memberships_user_id_status", table_name="account_memberships")
    op.drop_table("account_memberships")
    op.drop_table("profiles")
    op.drop_table("accounts")
