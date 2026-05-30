from pybit.unified_trading import HTTP


def _usdt_from_coins(coins: list) -> float | None:
    for row in coins:
        if str(row.get("coin") or "").upper() != "USDT":
            continue
        for key in ("equity", "walletBalance", "availableToWithdraw"):
            raw = row.get(key)
            if raw is not None and str(raw).strip() != "":
                return float(raw)
    return None


def get_futures_balance(session: HTTP) -> float:
    """
    Баланс USDT на Unified Trading Account (futures/derivatives).
    """
    balance = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
    account = (balance.get("result") or {}).get("list") or []
    if not account:
        return 0.0

    row = account[0]
    for key in ("totalEquity", "totalWalletBalance"):
        raw = row.get(key)
        if raw is not None and float(raw) > 0:
            return float(raw)

    usdt = _usdt_from_coins(row.get("coin") or [])
    return float(usdt or 0.0)


def get_spot_balance(session: HTTP) -> float:
    balance = session.get_wallet_balance(accountType="SPOT", coin="USDT")
    account = (balance.get("result") or {}).get("list") or []
    if not account:
        return 0.0

    row = account[0]
    usdt = _usdt_from_coins(row.get("coin") or [])
    if usdt is not None:
        return float(usdt)

    raw = row.get("totalWalletBalance")
    return float(raw or 0.0)
