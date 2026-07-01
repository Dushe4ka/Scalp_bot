"""Главное меню бота (единая точка навигации)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.languages._lang_func import get_config_lang
from bot.utils.onboarding import build_onboarding_checklist
from config import URL_TGCHANNEL, ADMIN_IDS
from database.users_repository import db


async def build_main_menu_keyboard(user_id: int, lang: str) -> InlineKeyboardMarkup:
    cfg = await get_config_lang(lang)
    is_subscriber = await db.is_subscriber(user_id)
    wait_confirm = await db.is_wait_sub_confirmation(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["start_btn"]["url_tg"], url=URL_TGCHANNEL)

    if is_subscriber and not wait_confirm:
        kb.button(text=cfg["start_btn"]["personal_account"], callback_data="profile_menu")
    elif wait_confirm:
        kb.button(text=cfg["start_btn"]["onboarding_setup"], callback_data="profile_menu")
    else:
        kb.button(text=cfg["start_btn"]["onboarding_progress"], callback_data="profile_menu")

    if is_subscriber and not wait_confirm:
        kb.button(text=cfg["start_btn"]["prolong_subscription"], callback_data="prolong_subscription")
    elif not wait_confirm:
        kb.button(text=cfg["start_btn"]["subscription_buy"], callback_data="subscription_buy")

    if int(user_id) in ADMIN_IDS:
        kb.button(text=cfg["general"]["admin_panel"], callback_data="admin_menu")

    kb.button(text=cfg["general"]["change_language"], callback_data="start_menu")
    kb.adjust(1)
    return kb.as_markup()


async def build_welcome_about_text(lang: str) -> str:
    cfg = await get_config_lang(lang)
    return f"{cfg['start_text']['greeting']}\n\n{cfg['start_text']['welcome_intro']}"


async def build_main_menu_text(
    user_id: int,
    lang: str,
    *,
    help_intro_key: str = "greeting_help",
) -> str:
    cfg = await get_config_lang(lang)
    user = await db.get_user_by_username_or_id(user_id)
    is_subscriber = await db.is_subscriber(user_id)
    wait_confirm = await db.is_wait_sub_confirmation(user_id)

    st = cfg["start_text"]
    if help_intro_key == "greeting_help":
        parts = [st["greeting"], st[help_intro_key]]
    else:
        parts = [st[help_intro_key]]
    parts.extend(["", st["quick_start"]])
    checklist = build_onboarding_checklist(
        user,
        cfg,
        is_subscriber=is_subscriber,
        is_wait_confirm=wait_confirm,
    )
    parts.extend(["", checklist])
    return "\n".join(parts)


async def build_main_menu_view(
    user_id: int,
    lang: str,
    *,
    help_intro_key: str = "greeting_help",
) -> tuple[str, InlineKeyboardMarkup]:
    text = await build_main_menu_text(user_id, lang, help_intro_key=help_intro_key)
    markup = await build_main_menu_keyboard(user_id, lang)
    return text, markup
