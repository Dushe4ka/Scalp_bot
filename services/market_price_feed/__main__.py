"""Run centralized market price feed: python -m services.market_price_feed"""
from __future__ import annotations

import argparse
import os

import dotenv

from services.market_price_feed.dual_feed import DEFAULT_SYMBOLS, DualMarketFeed

dotenv.load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bybit dual WS feed → Redis Pub/Sub")
    parser.add_argument(
        "--symbols",
        type=str,
        default=os.getenv("MARKET_FEED_SYMBOLS", ",".join(DEFAULT_SYMBOLS)),
        help="Comma-separated symbols",
    )
    parser.add_argument("--tick-interval", type=float, default=1.0)
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    feed = DualMarketFeed(symbols=symbols)
    feed.run_forever(tick_interval=args.tick_interval)


if __name__ == "__main__":
    main()
