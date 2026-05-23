"""
Создание тестовых пользователей в MongoDB:
- 15 с ожиданием подтверждения подписки (user_buy_subscription_30_days);
- 15 активных подписчиков.

Запуск из корня проекта: python3 tests/db/ex_1.py
"""
import asyncio

from database.users_repository import UsersRepository, UsersRepositoryError

client = UsersRepository()

# Диапазон tg_id не должен пересекаться с реальными аккаунтами.
BASE_WAIT = 9_000_000_001
BASE_SUB = 9_000_000_016


async def main() -> None:
    await client.ensure_indexes()

    for i in range(15):
        tg = BASE_WAIT + i
        await client.get_or_create_user(tg_id=tg, name=f"wait_user_{i}", language="ru")
        await client.user_buy_subscription_30_days(tg)
        print(f"Ожидает подтверждения: tg_id={tg} name=wait_user_{i}")

    for i in range(15):
        tg = BASE_SUB + i
        await client.get_or_create_user(tg_id=tg, name=f"sub_user_{i}", language="ru")
        await client.update_subscription(tg, True)
        await client.update_wait_sub_confirmation(tg, False)
        try:
            await client.update_end_subscription_date_by_type(tg, "1 мес")
        except UsersRepositoryError as e:
            print(f"Предупреждение tg_id={tg} end_date: {e}")
        print(f"Подписчик: tg_id={tg} name=sub_user_{i}")

    print("Готово: 15 ожидающих подтверждения, 15 подписчиков.")


if __name__ == "__main__":
    asyncio.run(main())
