"""CallbackData для пагинированных списков в админке (aiogram 3.x)."""

from aiogram.filters.callback_data import CallbackData


ADMIN_LIST_PAGE_SIZE = 10
HISTORY_TRADES_PAGE_SIZE = 10


class WaitConfirmListPageCb(CallbackData, prefix="wclp"):
    page: int


class WaitConfirmUserCb(CallbackData, prefix="wclu"):
    tg_id: int


class SubscribersListPageCb(CallbackData, prefix="sblp"):
    page: int


class SubscribersUserCb(CallbackData, prefix="sblu"):
    tg_id: int


class HistoryTradesPageCb(CallbackData, prefix="htlp"):
    page: int


class HistoryTradeItemCb(CallbackData, prefix="htli"):
    page: int
    idx: int


class ActiveTradesPageCb(CallbackData, prefix="atlp"):
    page: int


class ActiveTradeItemCb(CallbackData, prefix="atli"):
    page: int
    idx: int


class AdminOpenUserCb(CallbackData, prefix="aopu"):
    tg_id: int
