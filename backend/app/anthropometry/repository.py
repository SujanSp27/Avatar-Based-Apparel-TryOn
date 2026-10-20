"""Atomic chart versions and estimated measurement records in MongoDB."""

import json
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError
from pymongo import DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from backend.app.anthropometry.schemas import ChartCreate, ExtractionResponse
from backend.app.config import ROOT, settings
from ml.errors import PipelineError


def unavailable(exc: PyMongoError) -> PipelineError:
    # Driver messages can contain server addresses/credentials; don't expose them.
    return PipelineError("measurement_database_unavailable", "The measurement MongoDB service is unavailable. Retry when the app database is running.", 503)


class MeasurementRepository:
    def __init__(self, client=None, database: str | None = None):
        self.client = client if client is not None else MongoClient(
            settings.mongodb_uri, serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000, socketTimeoutMS=5000, connect=False,
        )
        self.db = self.client[database or settings.mongodb_database]
        self.charts = self.db["brand_size_charts"]
        self.brands = self.db["measurement_brands"]
        self.measurements = self.db["body_measurements"]
        self._ready = False
        self._lock = Lock()

    def initialize(self):
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            try:
                self.db.command("ping")
                # All sizes are embedded in one immutable version. Readers can
                # never see a partially inserted chart, even on standalone MongoDB.
                self.charts.create_index(
                    [("brand_id", 1), ("apparel_id", 1), ("version", DESCENDING)],
                    unique=True, name="brand_apparel_version",
                )
                self.measurements.create_index("measurement_id", unique=True)
                for seed in ("anthropometry-demo-v1.json", "india-body-charts-v1.json"):
                    for payload in json.loads((ROOT / "data/brandCharts" / seed).read_text(encoding="utf-8")):
                        chart = ChartCreate.model_validate(payload)
                        document = chart.model_dump(mode="json")
                        key = {k: document[k] for k in ("brand_id", "apparel_id", "version")}
                        self.charts.update_one(key, {"$setOnInsert": document}, upsert=True)
                self.brands.create_index("brand_id", unique=True)
                for brand in json.loads((ROOT / "data/brandCharts/india-brand-catalog-v1.json").read_text(encoding="utf-8")):
                    self.brands.update_one({"brand_id": brand["brand_id"]}, {"$setOnInsert": brand}, upsert=True)
            except PyMongoError as exc:
                raise unavailable(exc) from exc
            self._ready = True

    def get_chart(self, brand_id: str, apparel_id: str, version: int | None = None) -> ChartCreate:
        self.initialize()
        query = {"brand_id": brand_id, "apparel_id": apparel_id}
        if version is not None:
            query["version"] = version
        try:
            document = self.charts.find_one(query, {"_id": 0}, sort=[("version", DESCENDING)])
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        if document is None:
            raise PipelineError("chart_missing", "No chart exists for this brand/apparel/version.", 404)
        try:
            return ChartCreate.model_validate(document)
        except ValidationError as exc:
            raise PipelineError("chart_invalid", "Stored chart is invalid; replace it with a valid version.", 500) from exc

    def create_chart(self, chart: ChartCreate) -> ChartCreate:
        self.initialize()
        try:
            latest = self.charts.find_one(
                {"brand_id": chart.brand_id, "apparel_id": chart.apparel_id},
                sort=[("version", DESCENDING)],
            )
            if latest and (
                chart.version <= latest["version"] or chart.category.value != latest["category"]
                or chart.gender != latest.get("gender", "unisex")
                or chart.market != latest.get("market", "UNSPECIFIED")
            ):
                raise PipelineError("chart_version", "Use a newer chart version with the same apparel category, gender and market.", 409)
            self.charts.insert_one(chart.model_dump(mode="json"))
        except DuplicateKeyError as exc:
            raise PipelineError("chart_version", "This chart version already exists and cannot be overwritten.", 409) from exc
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        return chart

    def list_charts(self, gender: str | None = None, market: str | None = None,
                    brand_id: str | None = None) -> list[dict]:
        self.initialize()
        query = {key: value for key, value in
                 (("gender", gender), ("market", market), ("brand_id", brand_id)) if value is not None}
        try:
            return list(self.charts.find(query, {"_id": 0, "sizes": 0}).sort(
                [("brand_id", 1), ("apparel_id", 1), ("version", -1)]
            ).limit(500))
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def list_brands(self) -> list[dict]:
        self.initialize()
        try:
            return list(self.brands.find({}, {"_id": 0}).sort("brand_name", 1))
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def save_measurement(self, measurement_id: str, response: ExtractionResponse):
        self.initialize()
        try:
            self.measurements.insert_one({
                "measurement_id": measurement_id, "created_at": datetime.now(timezone.utc),
                **response.model_dump(mode="json"),
            })
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def close(self):
        self.client.close()


repository = MeasurementRepository()


def get_repository() -> MeasurementRepository:
    repository.initialize()
    return repository
