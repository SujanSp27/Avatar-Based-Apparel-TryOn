import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import ROOT
from backend.app.models import Brand, ChartVersion, SizeRow
from backend.app.schemas import ChartCreate
from ml.errors import PipelineError


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def row_dict(row: SizeRow) -> dict:
    names = (
        "sizeLabel",
        "sortOrder",
        "chestMin",
        "chestMax",
        "waistMin",
        "waistMax",
        "hipMin",
        "hipMax",
        "shoulderMin",
        "shoulderMax",
    )
    return {name: getattr(row, snake(name)) for name in names}


def chart_dict(chart: ChartVersion) -> dict:
    return {
        "id": chart.id,
        "brandId": chart.brand_id,
        "garmentCategory": chart.garment_category,
        "version": chart.version,
        "source": chart.source,
        "units": chart.units,
        "chartType": chart.chart_type,
        "sizes": [row_dict(r) for r in sorted(chart.sizes, key=lambda r: r.sort_order)],
    }


def latest_chart(
    db: Session, brand_id: int, category: str, version: int | None = None
) -> ChartVersion:
    query = select(ChartVersion).where(
        ChartVersion.brand_id == brand_id, ChartVersion.garment_category == category
    )
    if version is not None:
        query = query.where(ChartVersion.version == version)
    chart = db.scalar(query.order_by(ChartVersion.version.desc()))
    if chart is None:
        raise PipelineError(
            "chart_missing", "No size chart exists for this brand and category.", 404
        )
    return chart


def create_chart(db: Session, brand_id: int, data: ChartCreate) -> ChartVersion:
    if not db.get(Brand, brand_id):
        raise PipelineError("brand_missing", "Brand not found.", 404)
    latest = db.scalar(
        select(ChartVersion.version)
        .where(
            ChartVersion.brand_id == brand_id,
            ChartVersion.garment_category == data.garmentCategory.value,
        )
        .order_by(ChartVersion.version.desc())
    )
    if latest is not None and data.version <= latest:
        raise PipelineError(
            "chart_version", "Chart versions are immutable. Supply a newer version.", 409
        )
    chart = ChartVersion(
        brand_id=brand_id,
        garment_category=data.garmentCategory.value,
        version=data.version,
        source=data.source,
        sizes=[SizeRow(**{snake(k): v for k, v in s.model_dump().items()}) for s in data.sizes],
    )
    db.add(chart)
    db.flush()
    return chart


def seed_database(db: Session) -> None:
    source = json.loads((ROOT / "data/brandCharts/demo-v1.json").read_text())
    for spec in source["brands"]:
        brand = db.scalar(select(Brand).where(Brand.slug == spec["slug"]))
        if brand:
            continue
        brand = Brand(name=spec["name"], slug=spec["slug"], is_demo=True)
        db.add(brand)
        db.flush()
        for category in ("t-shirt", "shirt", "dress", "trouser"):
            create_chart(
                db,
                brand.id,
                ChartCreate(
                    garmentCategory=category,
                    version=1,
                    source=source["source"],
                    sizes=spec["sizes"],
                ),
            )
    db.commit()
