from users_repository import UsersRepository
import asyncio

async def main():
    repo = UsersRepository()
    await repo.ensure_indexes()
    user = await repo.update_subscription(1395854084, True)
    user = await repo.update_wait_sub_confirmation(1395854084, False)
    print(user)

if __name__ == "__main__":
    asyncio.run(main())