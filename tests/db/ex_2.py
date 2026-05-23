from database.users_repository import db
import asyncio

async def main():
    list_candidates = await db.list_trading_candidates()

    print(list_candidates[2])

if __name__ == "__main__":
    asyncio.run(main())