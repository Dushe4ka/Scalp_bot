from pydantic import BaseModel

class SymbolRequest(BaseModel):
    symbol: str
