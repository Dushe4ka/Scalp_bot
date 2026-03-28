"""CallbackData для пагинированных списков в админке (aiogram 3.x)."""

from aiogram.filters.callback_data import CallbackData


ADMIN_LIST_PAGE_SIZE = 10


class WaitConfirmListPageCb(CallbackData, prefix="wclp"):
    page: int


class WaitConfirmUserCb(CallbackData, prefix="wclu"):
    tg_id: int


class SubscribersListPageCb(CallbackData, prefix="sblp"):
    page: int


class SubscribersUserCb(CallbackData, prefix="sblu"):
    tg_id: int
