from bybit_logic.bybit_func import session, position
from celery_app.tasks.notifications import send_notification_task
import os
import dotenv

dotenv.load_dotenv()

# SYMBOL = os.getenv("SYMBOL").upper()
SYMBOL = "Luna2usdt"
SYMBOL = SYMBOL.upper()

session = session.create_session()

result = position.result_position_info(SYMBOL, session)
send_notification_task.delay(result)
print(result)