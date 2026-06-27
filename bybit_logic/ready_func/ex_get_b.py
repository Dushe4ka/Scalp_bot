from bybit_logic.bybit_func import session, account
from bybit_logic.bybit_func.calculator import calculate_max_permitted_price
from bybit_logic.config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET
from config import USE_DEMO

if USE_DEMO:
    api_key = (DEMO_API_KEY or "").strip()
    api_secret = (DEMO_API_SECRET or "").strip()
else:
    api_key = (API_KEY or "").strip()
    api_secret = (API_SECRET or "").strip()

http_session = session.create_session(use_demo=USE_DEMO, api_key=api_key, api_secret=api_secret)

balance = account.get_futures_balance(http_session)
max_permitted_price = calculate_max_permitted_price(balance)
print(balance)
print(max_permitted_price)
