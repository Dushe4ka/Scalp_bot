from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.languages._lang_func import get_config_lang
from config import URL_TGCHANNEL, URL_TECH_SUPPORT

# -------------------------------------------------------------
# Start keyboards
# -------------------------------------------------------------

def start_menu_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Стартовое меню кнопок - выбор языка у пользователя
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Русский", callback_data="russian_lang")
    kb.button(text="English", callback_data="english_lang")
    kb.adjust(1)
    return kb

def russia_start_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Русское меню кнопок после выбора языка (start)
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Наш ТГ канал", url=URL_TGCHANNEL)
    kb.button(text="Личный кабинет", callback_data="profile_menu")
    kb.button(text="Приобрести подписку", callback_data="subscription_buy")
    kb.button(text="Назад", callback_data="start_menu")
    kb.adjust(1)
    return kb

def english_start_kb(user_id: int) -> InlineKeyboardBuilder:
    """
    Английское меню кнопок после выбора языка (start)
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Our TG channel", url=URL_TGCHANNEL)
    kb.button(text="Profile", callback_data="profile_menu")
    kb.button(text="Buy subscription", callback_data="subscription_buy")
    kb.button(text="Back", callback_data="start_menu")
    kb.adjust(1)
    return kb

async def greeting_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок после выбора языка (greeting)
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["start_btn"]["url_tg"], url=URL_TGCHANNEL)
    kb.button(text=(await get_config_lang(lang))["start_btn"]["personal_account"], callback_data="profile_menu")
    kb.button(text=(await get_config_lang(lang))["start_btn"]["subscription_buy"], callback_data="subscription_buy")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="start_menu")
    kb.adjust(1)
    return kb
# -------------------------------------------------------------
# Subscription keyboards
# -------------------------------------------------------------

async def subscription_buy_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок оплаты подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["paid"], callback_data="paid")
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["question"], callback_data="question")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def question_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок 'Что дальше?'
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscription_buy")
    kb.adjust(1)
    return kb

async def input_payment_id_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Меню кнопок ввода ID платежа
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["input_payment_id"], callback_data="input_payment_id")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="subscription_buy")
    kb.adjust(1)
    return kb

async def input_payment_id_back_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопка "Назад" в ввод ID платежа
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="paid")
    kb.adjust(1)
    return kb

async def confirm_payment_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки "Да ✓" / "Нет ✗" в подтверждение платежа
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["confirm_payment"], callback_data="confirm_payment")
    kb.button(text=(await get_config_lang(lang))["subscription_btn"]["reject_payment"], callback_data="input_payment_id")
    kb.adjust(1)
    return kb

async def confirm_payment_success_kb(lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки перехода в профиль после оплаты подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

# -------------------------------------------------------------
# Profile keyboards
# -------------------------------------------------------------

async def profile_menu_kb_without_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в профиле без подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["subscription_buy"], callback_data="subscription_buy")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def profile_menu_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в профиле с подпиской
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def profile_menu_wait_sub_confirmation_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в профиле ожидания подтверждения подписки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb
    
# -------------------------------------------------------------
# Admin keyboards
# -------------------------------------------------------------

async def admin_menu_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в админ-панели
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["users_list"], callback_data="users_list")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="greeting")
    kb.adjust(1)
    return kb

async def users_list_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в списке пользователей
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["wait_confirm"], callback_data="wait_confirm")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["subscribers"], callback_data="subscribers")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="admin_menu")
    kb.adjust(1)
    return kb

async def wait_confirm_kb(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """
    Кнопки в списке ожидающих подтверждения
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["wait_confirm_list"], callback_data="wait_confirm_list")
    kb.button(text=(await get_config_lang(lang))["admin_btn"]["search_by_username_id"], callback_data="search_by_username_id")
    kb.button(text=(await get_config_lang(lang))["general"]["back"], callback_data="users_list")
    kb.adjust(1)
    return kb
