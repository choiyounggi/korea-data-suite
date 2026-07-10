from pydantic import BaseModel


class Holiday(BaseModel):
    date: str  # YYYY-MM-DD
    name_ko: str
    name_en: str | None = None
    type: str  # public | substitute | temporary | election
