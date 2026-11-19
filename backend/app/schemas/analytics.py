"""
WasteWise AI – Analytics & Metrics Schemas
"""

from typing import List

from pydantic import BaseModel


class WasteReportsByCategoryPoint(BaseModel):
    category: str
    count: int


class CollectionStatusPoint(BaseModel):
    status: str
    count: int


class AnalyticsSummaryResponse(BaseModel):
    total_waste_logged_kg: float
    total_recycled_kg: float
    diversion_rate_pct: float
    co2_avoided_kg: float
    pending_pickups_count: int
    active_centers_count: int
    total_waste_reports: int = 0
    total_collection_requests: int = 0
    reports_by_category: List[WasteReportsByCategoryPoint] = []
    collection_status_breakdown: List[CollectionStatusPoint] = []
    is_demo_data: bool = False
    note: str = "Aggregated from live database records."


class MonthlyCollectionPoint(BaseModel):
    month: str
    collected_kg: float
    diverted_kg: float


class AnalyticsMonthlyResponse(BaseModel):
    period: str
    data: List[MonthlyCollectionPoint]
    is_demo_data: bool = False


class CategoryDistributionPoint(BaseModel):
    category: str
    share_pct: float
    volume_kg: float
    color_code: str


class AnalyticsCategoriesResponse(BaseModel):
    categories: List[CategoryDistributionPoint]
    is_demo_data: bool = False
