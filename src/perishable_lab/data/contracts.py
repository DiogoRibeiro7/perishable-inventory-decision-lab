"""Typed source contracts for retail replenishment data."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class VersionedSourceRecord(BaseModel):
    """Common metadata required for reproducible source-table ingestion."""

    source_primary_key: str = Field(min_length=1)
    business_date: date
    event_time: datetime
    ingestion_time: datetime
    revision: int = Field(default=0, ge=0)


class SalesTransaction(VersionedSourceRecord):
    """Observed sale that may be censored when shelf stock is unavailable."""

    store_id: str = Field(min_length=1)
    source_product_id: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    gross_sales: float = Field(default=0.0, ge=0.0)


class StockSnapshot(VersionedSourceRecord):
    """Recorded inventory snapshot from a store system."""

    store_id: str = Field(min_length=1)
    source_product_id: str = Field(min_length=1)
    on_hand_quantity: int


class WasteEvent(VersionedSourceRecord):
    """Recorded disposal or shrinkage event."""

    store_id: str = Field(min_length=1)
    source_product_id: str = Field(min_length=1)
    waste_quantity: int = Field(ge=0)
    waste_reason: str = "unknown"


class DeliveryEvent(VersionedSourceRecord):
    """Supplier delivery receipt."""

    store_id: str = Field(min_length=1)
    source_product_id: str = Field(min_length=1)
    delivered_quantity: int = Field(ge=0)
    supplier_id: str = Field(min_length=1)


class PlacedOrder(VersionedSourceRecord):
    """Order placed by a system or store user."""

    store_id: str = Field(min_length=1)
    source_product_id: str = Field(min_length=1)
    ordered_quantity: int = Field(ge=0)
    expected_delivery_date: date
    supplier_id: str = Field(min_length=1)


class ProductMaster(BaseModel):
    """Slowly changing product attributes used by forecasts and policies."""

    source_product_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None
    shelf_life_days: int = Field(ge=1)
    lead_time_days: int = Field(ge=0)
    unit_cost: float = Field(ge=0.0)
    unit_margin: float = Field(ge=0.0)
    waste_cost: float = Field(ge=0.0)


class SupplierProductMapping(BaseModel):
    """Mapping from supplier item identifiers to stable product identifiers."""

    supplier_id: str = Field(min_length=1)
    supplier_product_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None


class Promotion(BaseModel):
    """Promotion information available before a decision is made."""

    business_date: date
    store_id: str = Field(min_length=1)
    source_product_id: str = Field(min_length=1)
    promotion: int = Field(ge=0, le=1)
    known_at: datetime


class Price(BaseModel):
    """Store-product price available before a decision is made."""

    business_date: date
    store_id: str = Field(min_length=1)
    source_product_id: str = Field(min_length=1)
    price: float = Field(gt=0.0)
    known_at: datetime


class StoreCalendar(BaseModel):
    """Store opening status for a business date."""

    business_date: date
    store_id: str = Field(min_length=1)
    is_open: bool = True


class DeliveryCalendar(BaseModel):
    """Supplier delivery availability for a store-product date."""

    business_date: date
    store_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    can_deliver: bool = True


__all__ = [
    "DeliveryCalendar",
    "DeliveryEvent",
    "PlacedOrder",
    "Price",
    "ProductMaster",
    "Promotion",
    "SalesTransaction",
    "StockSnapshot",
    "StoreCalendar",
    "SupplierProductMapping",
    "VersionedSourceRecord",
    "WasteEvent",
]
