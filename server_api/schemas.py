from pydantic import BaseModel

class SymbolRequest(BaseModel):
    symbol: str


class CustomAlgoLaunchRequest(BaseModel):
    symbol: str
    tg_id: int
    order_amount_override: float | None = None
