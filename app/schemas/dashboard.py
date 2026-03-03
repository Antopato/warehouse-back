from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_products: int
    total_categories: int
    total_users: int
    total_margin: float
    total_stock_value: float
    low_stock_count: int


class LowStockProduct(BaseModel):
    code: str
    name: str
    quantity: int
    location: str | None


class RecentProduct(BaseModel):
    code: str
    name: str
    quantity: int
    created_at: str


class DashboardResponse(BaseModel):
    stats: DashboardStats
    low_stock_products: list[LowStockProduct]
    recent_products: list[RecentProduct]
