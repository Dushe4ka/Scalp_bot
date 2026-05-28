from pydantic import BaseModel

class SymbolRequest(BaseModel):
    symbol: str


class UserSymbolRequest(BaseModel):
    tg_id: int
    symbol: str


class UserRequest(BaseModel):
    tg_id: int


class CustomAlgoLaunchRequest(BaseModel):
    symbol: str
    tg_id: int
    order_amount_override: float | None = None
