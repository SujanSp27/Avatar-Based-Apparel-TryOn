"""Atomic chart versions and estimated measurement records in MongoDB."""

import json
from datetime import datetime, timezone
from threading import RLock

from pydantic import ValidationError
from pymongo import DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from backend.app.anthropometry.schemas import (
    BrandCreate,
    BrandUpdate,
    ChartCreate,
    ExtractionResponse,
    MeasurementPage,
    StoredMeasurement,
)
from backend.app.config import ROOT, settings
from ml.errors import PipelineError


def unavailable(exc: PyMongoError) -> PipelineError:
    # Driver messages can contain server addresses/credentials; don't expose them.
    return PipelineError("measurement_database_unavailable", "The measurement MongoDB service is unavailable. Retry when the app database is running.", 503)


class MeasurementRepository:
    def __init__(self, client=None, database: str | None = None):
        self._external_client = client is not None
        self._database_name = database or settings.mongodb_database
        self._lock = RLock()
        self._closed = False
        self._bind(client if client is not None else self._new_client())

    @staticmethod
    def _new_client():
        return MongoClient(
            settings.mongodb_uri, serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000, socketTimeoutMS=5000, connect=False, tz_aware=True,
        )

    def _bind(self, client):
        self.client = client
        self.db = self.client[self._database_name]
        self.charts = self.db["brand_size_charts"]
        self.brands = self.db["measurement_brands"]
        self.measurements = self.db["body_measurements"]
        self._ready = False

    def initialize(self):
        if self._ready:
            return
        with self._lock:
            if self._closed:
                if self._external_client:
                    raise PipelineError("measurement_database_unavailable", "Database connection is closed.", 503)
                self._bind(self._new_client())
                self._closed = False
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
                self.measurements.create_index([("created_at", DESCENDING), ("measurement_id", 1)])
                for seed in ("anthropometry-demo-v1.json", "india-body-charts-v1.json", "sourced-body-charts-v2.json"):
                    for payload in json.loads((ROOT / "data/brandCharts" / seed).read_text(encoding="utf-8")):
                        chart = ChartCreate.model_validate(payload)
                        document = chart.model_dump(mode="json")
                        key = {k: document[k] for k in ("brand_id", "apparel_id", "version")}
                        self.charts.update_one(key, {"$setOnInsert": document}, upsert=True)
                self.brands.create_index("brand_id", unique=True)
                for brand in json.loads((ROOT / "data/brandCharts/india-brand-catalog-v1.json").read_text(encoding="utf-8")):
                    self.brands.update_one({"brand_id": brand["brand_id"]}, {"$setOnInsert": brand}, upsert=True)
                for brand in json.loads((ROOT / "data/brandCharts/brand-directory-v2.json").read_text(encoding="utf-8")):
                    self.brands.update_one({"brand_id": brand["brand_id"]}, {"$setOnInsert": brand}, upsert=True)
                # Demo and admin-created chart brands are discoverable too.
                for chart in self.charts.find({}, {"brand_id": 1, "brand_name": 1, "market": 1, "is_demo": 1}):
                    self.brands.update_one({"brand_id": chart["brand_id"]}, {"$setOnInsert": {
                        "brand_id": chart["brand_id"], "brand_name": chart["brand_name"],
                        "market": chart.get("market", "UNSPECIFIED"), "is_demo": chart.get("is_demo", False),
                        "coverage": [],
                    }}, upsert=True)
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
        # One API process is supported. Serialize concurrent version requests;
        # MongoDB's unique index additionally prevents duplicate version writes.
        with self._lock:
            return self._insert_chart(chart)

    def _insert_chart(self, chart: ChartCreate) -> ChartCreate:
        try:
            brand = self.brands.find_one({"brand_id": chart.brand_id})
            if brand and brand["brand_name"] != chart.brand_name:
                raise PipelineError("brand_mismatch", "Chart brand_name must match the registered brand.", 409)
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
            self.brands.update_one({"brand_id": chart.brand_id}, {"$setOnInsert": {
                "brand_id": chart.brand_id, "brand_name": chart.brand_name,
                "market": chart.market, "is_demo": chart.is_demo, "coverage": [],
            }}, upsert=True)
        except DuplicateKeyError as exc:
            raise PipelineError("chart_version", "This chart version already exists and cannot be overwritten.", 409) from exc
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        return chart

    def list_charts(self, gender: str | None = None, market: str | None = None,
                    brand_id: str | None = None, category: str | None = None,
                    limit: int = 100, offset: int = 0, latest_only: bool = False) -> list[dict]:
        self.initialize()
        query = {key: value for key, value in
                 (("gender", gender), ("market", market), ("brand_id", brand_id), ("category", category)) if value is not None}
        try:
            if latest_only:
                return list(self.charts.aggregate([
                    {"$match": query}, {"$sort": {"brand_id": 1, "apparel_id": 1, "version": -1}},
                    {"$group": {"_id": {"brand": "$brand_id", "apparel": "$apparel_id"}, "chart": {"$first": "$$ROOT"}}},
                    {"$replaceRoot": {"newRoot": "$chart"}}, {"$sort": {"brand_id": 1, "apparel_id": 1}},
                    {"$skip": offset}, {"$limit": limit}, {"$project": {"_id": 0, "sizes": 0}},
                ]))
            return list(self.charts.find(query, {"_id": 0, "sizes": 0}).sort(
                [("brand_id", 1), ("apparel_id", 1), ("version", -1)]
            ).skip(offset).limit(limit))
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def list_brands(self, include_demo: bool = False) -> list[dict]:
        self.initialize()
        try:
            query = {} if include_demo else {"is_demo": {"$ne": True}}
            return [self._brand_with_charts(brand) for brand in self.brands.find(query, {"_id": 0}).sort("brand_name", 1)]
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def _brand_with_charts(self, brand: dict) -> dict:
        # Source verification notes remain distinct from admin-supplied charts.
        charts = self.list_charts(brand_id=brand["brand_id"], latest_only=True, limit=500)
        return {**brand, "available_charts": charts,
                "recommendation_available": any(c.get("measurement_basis", "body") == "body" for c in charts)}

    def get_brand(self, brand_id: str) -> dict:
        self.initialize()
        try:
            brand = self.brands.find_one({"brand_id": brand_id}, {"_id": 0})
            if brand is None:
                raise PipelineError("brand_missing", "This measurement brand was not found.", 404)
            return self._brand_with_charts(brand)
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def create_brand(self, brand: BrandCreate) -> dict:
        self.initialize()
        try:
            self.brands.insert_one({**brand.model_dump(mode="json"), "coverage": [], "is_demo": False})
        except DuplicateKeyError as exc:
            raise PipelineError("brand_conflict", "This brand ID already exists.", 409) from exc
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        return self.get_brand(brand.brand_id)

    def update_brand(self, brand_id: str, update: BrandUpdate) -> dict:
        self.initialize()
        try:
            result = self.brands.update_one({"brand_id": brand_id}, {"$set": update.model_dump(mode="json", exclude_unset=True)})
            if result.matched_count == 0:
                raise PipelineError("brand_missing", "This measurement brand was not found.", 404)
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        # Historical chart provenance retains its original brand name.
        return self.get_brand(brand_id)

    def list_versions(self, brand_id: str, apparel_id: str) -> list[dict]:
        self.get_chart(brand_id, apparel_id)
        try:
            return list(self.charts.find({"brand_id": brand_id, "apparel_id": apparel_id},
                                        {"_id": 0, "sizes": 0}).sort("version", -1))
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def save_measurement(self, measurement_id: str, response: ExtractionResponse):
        self.initialize()
        try:
            self.measurements.insert_one({
                **response.model_dump(mode="json"),
                "measurement_id": measurement_id, "created_at": datetime.now(timezone.utc),
            })
        except PyMongoError as exc:
            raise unavailable(exc) from exc

    def get_measurement(self, measurement_id: str) -> StoredMeasurement:
        self.initialize()
        try:
            record = self.measurements.find_one({"measurement_id": measurement_id}, {"_id": 0})
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        if record is None:
            raise PipelineError("measurement_missing", "This measurement record was not found.", 404)
        try:
            return StoredMeasurement.model_validate(record)
        except ValidationError as exc:
            raise PipelineError("measurement_record_invalid", "The stored measurement record is invalid.", 500) from exc

    def list_measurements(self, limit: int = 20, offset: int = 0) -> MeasurementPage:
        self.initialize()
        try:
            records = list(self.measurements.find({}, {"_id": 0}).sort(
                [("created_at", -1), ("measurement_id", 1)]).skip(offset).limit(limit))
            return MeasurementPage(items=records, total=self.measurements.count_documents({}), limit=limit, offset=offset)
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        except ValidationError as exc:
            raise PipelineError("measurement_record_invalid", "A stored measurement record is invalid.", 500) from exc

    def delete_measurement(self, measurement_id: str):
        self.initialize()
        try:
            result = self.measurements.delete_one({"measurement_id": measurement_id})
        except PyMongoError as exc:
            raise unavailable(exc) from exc
        if not result.deleted_count:
            raise PipelineError("measurement_missing", "This measurement record was not found.", 404)

    def ping(self) -> bool:
        try:
            self.initialize()
            self.db.command("ping")
            return True
        except (PipelineError, PyMongoError):
            return False

    def close(self):
        with self._lock:
            self.client.close()
            self._ready = False
            self._closed = True


repository = MeasurementRepository()


def get_repository() -> MeasurementRepository:
    repository.initialize()
    return repository
