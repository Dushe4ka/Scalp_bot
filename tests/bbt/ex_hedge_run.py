from bybit_logic.api_algorithms.hedge_long_short_bu_ts import start_trading

# Задаем символ отдельно, можно быстро менять перед запуском.
SYMBOL = "HIGHUSDT"


def run_hedge(symbol: str = SYMBOL) -> None:
    start_trading(symbol=symbol)


if __name__ == "__main__":
    run_hedge()
