from bybit_logic.bybit_func import session, position
import os
import dotenv

dotenv.load_dotenv()

SYMBOL = os.getenv("SYMBOL").upper()

session = session.create_session()

result = position.if_position_open(session, SYMBOL)
if result:
    print(f"✅ Позиция открыта: {result}")
else:
    print("❌ Позиция закрыта")
