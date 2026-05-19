"""Run centralized market price feed: python -m services.market_price_feed"""
from __future__ import annotations

import argparse

import dotenv

from services.market_price_feed.dual_feed import DualMarketFeed

dotenv.load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bybit dual WS feed → Redis (dynamic symbol subscribe on signal)"
    )
    parser.add_argument("--tick-interval", type=float, default=1.0)
    args = parser.parse_args()
    feed = DualMarketFeed()
    feed.run_forever(tick_interval=args.tick_interval)


if __name__ == "__main__":
    main()
