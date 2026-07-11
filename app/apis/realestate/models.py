from pydantic import BaseModel


class Transaction(BaseModel):
    property_type: str  # apartment | officetel | land
    trade_type: str  # sale | jeonse | monthly_rent
    region_code: str  # 5-digit LAWD code
    neighborhood: str | None = None
    building_name: str | None = None
    traded_on: str  # YYYY-MM-DD
    price_won: int | None = None
    deposit_won: int | None = None
    monthly_rent_won: int | None = None
    area_m2: float | None = None
    floor: int | None = None
    built_year: int | None = None
