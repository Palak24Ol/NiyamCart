from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    brand: str
    category: str
    audience: str
    description: str
    price_paise: int = Field(ge=0)
    original_price_paise: int = Field(ge=0)
    rating: float = Field(ge=0, le=5)
    reviews: int = Field(ge=0)
    stock: int = Field(ge=0)
    delivery_days: int = Field(ge=0)
    free_delivery: bool
    occasion: str
    material: str
    highlights: list[str]
    badges: list[str]
    specs: dict[str, object]
    size_chart: dict[str, object] | None
    return_window_days: int = Field(ge=0)
    image: str
    version: int = Field(ge=1)


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    count: int = Field(ge=0)


class CompatibleAddonItem(BaseModel):
    product_id: str
    rule_id: str
    reason: str


class CompatibleAddonListResponse(BaseModel):
    primary_product_id: str
    items: list[CompatibleAddonItem]
    count: int = Field(ge=0)
