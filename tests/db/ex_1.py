from pydoc import cli
from users_repository import UsersRepository
import asyncio

client = UsersRepository()

async def main():
    await client.ensure_indexes()

    user = await client.get_or_create_user(
        tg_id=12345,
        name="davidi",
        language="ru"
    )
    await client.update_language(12345, "en")
    await client.update_subscription(12345, True)

if __name__ == "__main__":
    asyncio.run(main())