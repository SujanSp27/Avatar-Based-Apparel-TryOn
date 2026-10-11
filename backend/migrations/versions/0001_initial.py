"""Normalized versioned brand charts and persisted pipeline runs."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # This revision is intentionally independent of live ORM definitions.
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "size_chart_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("garment_category", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("units", sa.String(5), nullable=False),
        sa.Column("chart_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brand_id", "garment_category", "version"),
        sa.CheckConstraint("version > 0"),
    )
    op.create_index("ix_size_chart_versions_brand_id", "size_chart_versions", ["brand_id"])
    op.create_table(
        "size_charts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "chart_id",
            sa.Integer(),
            sa.ForeignKey("size_chart_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("size_label", sa.String(20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("chest_min", sa.Float(), nullable=False),
        sa.Column("chest_max", sa.Float(), nullable=False),
        sa.Column("waist_min", sa.Float(), nullable=False),
        sa.Column("waist_max", sa.Float(), nullable=False),
        sa.Column("hip_min", sa.Float(), nullable=False),
        sa.Column("hip_max", sa.Float(), nullable=False),
        sa.Column("shoulder_min", sa.Float(), nullable=True),
        sa.Column("shoulder_max", sa.Float(), nullable=True),
        sa.UniqueConstraint("chart_id", "size_label"),
        sa.UniqueConstraint("chart_id", "sort_order"),
        sa.CheckConstraint("chest_min > 0 AND chest_max >= chest_min"),
        sa.CheckConstraint("waist_min > 0 AND waist_max >= waist_min"),
        sa.CheckConstraint("hip_min > 0 AND hip_max >= hip_min"),
        sa.CheckConstraint(
            "shoulder_min IS NULL OR (shoulder_min > 0 AND shoulder_max >= shoulder_min)"
        ),
    )
    op.create_table(
        "tryon_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chart_id", sa.Integer(), sa.ForeignKey("size_chart_versions.id"), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("tryon_runs")
    op.drop_table("size_charts")
    op.drop_index("ix_size_chart_versions_brand_id", table_name="size_chart_versions")
    op.drop_table("size_chart_versions")
    op.drop_table("brands")
