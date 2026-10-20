from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ChartVersion(Base):
    __tablename__ = "size_chart_versions"
    __table_args__ = (
        UniqueConstraint("brand_id", "garment_category", "version"),
        CheckConstraint("version > 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    garment_category: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(500))
    units: Mapped[str] = mapped_column(String(5), default="cm")
    chart_type: Mapped[str] = mapped_column(String(30), default="body_measurements")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    sizes: Mapped[list["SizeRow"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class SizeRow(Base):
    __tablename__ = "size_charts"
    __table_args__ = (
        UniqueConstraint("chart_id", "size_label"),
        UniqueConstraint("chart_id", "sort_order"),
        CheckConstraint("chest_min > 0 AND chest_max >= chest_min"),
        CheckConstraint("waist_min > 0 AND waist_max >= waist_min"),
        CheckConstraint("hip_min > 0 AND hip_max >= hip_min"),
        CheckConstraint(
            "shoulder_min IS NULL OR (shoulder_min > 0 AND shoulder_max >= shoulder_min)"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    chart_id: Mapped[int] = mapped_column(ForeignKey("size_chart_versions.id", ondelete="CASCADE"))
    size_label: Mapped[str] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(Integer)
    chest_min: Mapped[float] = mapped_column(Float)
    chest_max: Mapped[float] = mapped_column(Float)
    waist_min: Mapped[float] = mapped_column(Float)
    waist_max: Mapped[float] = mapped_column(Float)
    hip_min: Mapped[float] = mapped_column(Float)
    hip_max: Mapped[float] = mapped_column(Float)
    shoulder_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    shoulder_max: Mapped[float | None] = mapped_column(Float, nullable=True)


class Run(Base):
    __tablename__ = "tryon_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    chart_id: Mapped[int | None] = mapped_column(
        ForeignKey("size_chart_versions.id"), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BrandSizeChart(Base):
    """Six-metric apparel charts for /api/v1; legacy charts retain their contract."""

    __tablename__ = "brand_size_charts"
    __table_args__ = (
        UniqueConstraint("brand_id", "apparel_id", "version", "size_label"),
        UniqueConstraint("brand_id", "apparel_id", "version", "sort_order"),
        CheckConstraint("version > 0 AND sort_order >= 0"),
        *(
            CheckConstraint(
                f"({metric}_min IS NULL AND {metric}_max IS NULL) OR "
                f"({metric}_min IS NOT NULL AND {metric}_max IS NOT NULL AND "
                f"{metric}_min > 0 AND {metric}_max >= {metric}_min)",
                name=f"ck_brand_size_{metric}",
            )
            for metric in ("shoulder_width", "chest_circumference", "waist_circumference",
                           "hip_circumference", "thigh_circumference", "inseam_length")
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[str] = mapped_column(String(120), index=True)
    brand_name: Mapped[str] = mapped_column(String(120))
    apparel_id: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(20))
    size_label: Mapped[str] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(500))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    shoulder_width_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    shoulder_width_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    chest_circumference_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    chest_circumference_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    waist_circumference_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    waist_circumference_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    hip_circumference_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    hip_circumference_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    thigh_circumference_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    thigh_circumference_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    inseam_length_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    inseam_length_max: Mapped[float | None] = mapped_column(Float, nullable=True)
