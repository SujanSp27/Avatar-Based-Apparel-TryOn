"""Index owner-filtered result history without rewriting or assigning old data."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE INDEX ix_tryon_owner_created ON tryon_runs ((metadata_json ->> 'owner'), created_at DESC)")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("CREATE INDEX ix_tryon_owner_created ON tryon_runs (json_extract(metadata_json, '$.owner'), created_at DESC)")


def downgrade():
    op.drop_index("ix_tryon_owner_created", table_name="tryon_runs")
