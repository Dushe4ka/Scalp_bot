from pydoc import cli
from users_repository import UsersRepository
import asyncio

client = UsersRepository()

async def main():
    await client.ensure_indexes()

    # user1 = await client.get_or_create_user(
    #     tg_id=123,
    #     name="test1",
    #     language="ru"
    # )
    # user2 = await client.get_or_create_user(
    #     tg_id=1234,
    #     name="test2",
    #     language="ru"
    # )
    # user3 = await client.get_or_create_user(
    #     tg_id=12345,
    #     name="test3",
    #     language="ru"
    # )
    # user4 = await client.get_or_create_user(
    #     tg_id=123456,
    #     name="test4",
    #     language="ru"
    # )
    # user5 = await client.get_or_create_user(
    #     tg_id=1234567,
    #     name="test5",
    #     language="ru"
    # )
    # user6 = await client.get_or_create_user(
    #     tg_id=12345678,
    #     name="test6",
    #     language="ru"
    # )
    # user7 = await client.get_or_create_user(
    #     tg_id=123456789,
    #     name="test7",
    #     language="ru"
    # )
    # user8 = await client.get_or_create_user(
    #     tg_id=1234567890,
    #     name="test8",
    #     language="ru"
    # )
    # user9 = await client.get_or_create_user(
    #     tg_id=12345678901,
    #     name="test9",
    #     language="ru"
    # )
    # user10 = await client.get_or_create_user(
    #     tg_id=123456789012,
    #     name="test10",
    #     language="ru"
    # )
    # update_user1 = await client.user_buy_subscription_30_days(
    #     tg_id=123,
    # )
    # update_user2 = await client.user_buy_subscription_30_days(
    #     tg_id=1234,
    # )
    # update_user3 = await client.user_buy_subscription_30_days(
    #     tg_id=12345,
    # )
    # update_user4 = await client.user_buy_subscription_30_days(
    #     tg_id=123456,
    # )
    # update_user5 = await client.user_buy_subscription_30_days(
    #     tg_id=1234567,
    # )
    # update_user6 = await client.user_buy_subscription_30_days(
    #     tg_id=12345678,
    # )
    # update_user7 = await client.user_buy_subscription_30_days(
    #     tg_id=123456789,
    # )
    # update_user8 = await client.user_buy_subscription_30_days(
    #     tg_id=1234567890,
    # )
    # update_user9 = await client.user_buy_subscription_30_days(
    #     tg_id=12345678901,
    # )
    # update_user10 = await client.user_buy_subscription_30_days(
    #     tg_id=123456789012,
    # )
    
    # await client.update_language(12345, "en")
    # await client.update_subscription(12345, True)
    user = await client.get_user_by_username_or_id(7810248592)
    print(user)

if __name__ == "__main__":
    asyncio.run(main())