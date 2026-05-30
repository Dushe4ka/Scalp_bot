from config import URL_PAYMENT

RU_CONFIGURATION = {
  "start_text": {
    "greeting": "Здравствуйте! Меня зовут ZdormanBot 👋\nЯ расскажу, как приобрести подписку на наш сервис 📈 и почему нам стоит верить 😎",
  },
  "start_btn": {
    "url_tg": "Наш ТГ канал",
    "personal_account": "Личный кабинет",
    "subscription_buy": "Приобрести подписку",
    "prolong_subscription": "Продлить подписку",
  }, # -------------------------------------------------------------
  "subscription_text": {
    "buy_info": f"Оплата 1 месяц = 49$\nURL кошелька - {URL_PAYMENT}\nТип оплаты TRC-20\n P.S. Оплата принимается только с аккаунтов бирж.\nПосле оплаты нажмите на кнопку «Оплатил». и введите ID платежа.",
    "question": "После оплаты нажмите на кнопку «Оплатил». и введите ID платежа. Далее администрация в течении 24ч проверит ваш платеж и активирует вашу подписку.",
    "prolong_question": "После оплаты нажмите на кнопку «Оплатил». и введите ID платежа. Далее администрация в течении 24ч проверит ваш платеж и продлит вашу подписку.",
    "paid": "Отлично! Осталось ввести ID платежа. Для этого нажмите на кнопку «Ввести ID платежа» и введите ID платежа.\nДалее администрация в течении 24ч проверит ваш платеж и активирует вашу подписку.",
    "prolong_paid": "Отлично! Осталось ввести ID платежа. Для этого нажмите на кнопку «Ввести ID платежа» и введите ID платежа.\nДалее администрация в течении 24ч проверит ваш платеж и продлит вашу подписку.",
    "input_payment_id": "Введите ID платежа в чат",
    "confirm_payment": "Все верно: {payment_id}",
    "confirm_payment_success": "Спасибо за оплату! Администрация в течении 24ч проверит ваш платеж и активирует вашу подписку.",
    "prolong_confirm_payment_success": "Спасибо за оплату! Администрация в течении 24ч проверит ваш платеж и продлит вашу подписку.",
    "prolong_subscription": f"Продление подписки🚀\n\nОплата 1 месяц = 49$\nURL кошелька - {URL_PAYMENT}\nТип оплаты TRC-20\n P.S. Оплата принимается только с аккаунтов бирж.\nПосле оплаты нажмите на кнопку «Оплатил». и введите ID платежа.",
    "subscription_reminder_3d": (
        "Уважаемый подписчик нашего сервиса!\n\n"
        "Через 3 дня ({end_date}) закончится ваша подписка.\n"
        "Продлите подписку в боте, чтобы торговля не прерывалась."
    ),
    "subscription_reminder_1d": (
        "Уважаемый подписчик нашего сервиса!\n\n"
        "Через 1 день ({end_date}) закончится ваша подписка.\n"
        "Продлите подписку в боте, чтобы не потерять доступ к алгоритму."
    ),
    "subscription_expired": (
        "Уважаемый подписчик нашего сервиса!\n\n"
        "Ваша подписка истекла ({end_date}) и была отключена.\n"
        "Для продолжения работы оформите или продлите подписку в боте."
    ),
  },
  "subscription_btn": {
    "paid": "Оплатил",
    "question": "Что дальше?",
    "input_payment_id": "Ввести ID платежа",
    "confirm_payment": "Да ✓",
    "reject_payment": "Нет ✗",
  }, # -------------------------------------------------------------
  "profile_text": {
    "profile_menu": "Мой профиль 👤\nДата оформления подписки: {payment_date}\nТип подписки: {subscription_type}\nЦена сделки: {sum_for_trades}\nAPI ключ указан: {api_key}",
    "profile_menu_without_subscription": "Мой профиль 👤\n\n🚫 Подписка не оформленa\n💬 Нажмите на кнопку ниже и следуйте инструкции чтобы оформить подписку",
    "profile_menu_wait_sub_confirmation": "Мой профиль 👤\n\n🎉 Спасибо за оплату! \n🕒 Ожидание подтверждения подписки\n💬 Пожалуйста, подождите 24 часа для подтверждения вашего платежа",
    "profile_statistics": "📊 Статистика \n\nОбщее количество сделок: {total_trades}\nОбщий PnL: {total_pnl}\nКоличество + сделок: {positive_trades}\nЗаработанная суммка с + сделок: {sum_positive_trades}\n Количество - сделок: {negative_trades}\nПроигранная сумма с - сделок: {sum_negative_trades}",
    "profile_settings": "⚙️ Настройки \n\nAPI ключ: {api_key}\nAPI секрет: {api_secret}\nСумма для открытия сделки: {sum_for_trades}",
    "profile_settings_api_key": "Введите новый API ключ",
    "profile_settings_api_secret": "Введите новый API секрет",
    "profile_settings_sum_for_trades": "Введите новую сумму сделки\n\nРекомендуемая сумма сделки: {recommended_usdt} USDT",
    "profile_settings_sum_for_trades_fallback": "Введите новую сумму сделки",
    "profile_settings_sum_for_trades_risk_warning": "⚠️ Вы уверены?\n\nВы ввели: {entered_sum} USDT\nРекомендуемая сумма: {recommended_usdt} USDT\n\nВыставленное значение ведет к повышенным рискам при работе алгоритма.",
    "profile_balance": "💰 Баланс futures аккаунта: {balance} USDT",
    "profile_balance_api_missing": "❌ Не удалось получить баланс: в настройках профиля не указаны API key/secret.",
    "profile_balance_error": "❌ Не удалось получить баланс. Попробуйте позже.",
    "profile_history_trades_title": "📋 История сделок (последние {count})",
    "profile_history_trades_page": "Стр. {page}/{pages} · всего {total}",
    "profile_history_trades_empty": "📋 История сделок пуста.",
    "profile_history_trades_error": "❌ Не удалось получить историю сделок. Попробуйте позже.",
    "profile_history_trade_details_title": "📄 Сделка",
    "trading_menu": "📈 Торговля\n\nВыберите действие:",
    "active_trades_page_title": "🟢 Активные сделки\nСтр. {page}/{pages} · всего {total}",
    "active_trades_empty": "🟢 Активных сделок нет.",
    "active_trades_error": "❌ Не удалось получить активные сделки. Попробуйте позже.",
    "active_trade_details_title": "📄 Активная сделка",
    "active_trade_not_found": "❌ Не удалось получить данные по активной сделке {symbol}.",
    "active_trade_stop_success": "🛑 Торговля по {symbol} остановлена.\n{message}",
    "active_trade_stop_error": "❌ Не удалось остановить торговлю по {symbol}.",
    "stop_all_trading_success": "🛑 Вся торговля остановлена.\n{message}",
    "stop_all_trading_error": "❌ Не удалось остановить всю торговлю.",
  },
  "profile_btn": {
    "subscription_buy": "Приобрести подписку",
    "tech_support": "Тех. поддержка",
    "statistics": "📊 Статистика", # ----
    "settings_profile": "⚙️ Настройки", # ---
    "edit_api_key_secret": "🔑 API Key / Secret",
    "edit_sum_for_trades": "💵 Сумма сделки",
    "trading": "📈 Торговля", # ----
    "active_trades": "🟢 Активные сделки",
    "stop_all_trading": "🛑 Остановить всю торговлю",
    "stop_current_trade": "🛑 Остановить текущую торговлю",
    "pause_trading": "⏸️ Приостановить торговлю",
    "resume_trading": "▶️ Продолжить торговлю",
    "stop_trading": "🛑 Остановить алгоритм",
    "name_coin_stop": "По названию монеты",
    "trading_portfolio": "💰 Баланс", # ----
    "history_trades": "📋 История сделок", # ----
    "trades_list": "Список сделок",
    "export_csv": "Экспорт CSV",
    "confirm_risk_sum_for_trades": "✅ Да, установить сумму",
    "cancel_risk_sum_for_trades": "✏️ Нет, ввести другую",
  }, # -------------------------------------------------------------
  "admin_text": {
    "admin_menu": "Админ-панель 👨‍💻\n\nВыберите действие:",
    "users_list": "Пользователи👥\n\nВыберите тип пользователей с которыми будете работать",
    "statistics_project": "Статистика📊\n\nОбщее количество пользователей: {total_users}\nКоличество подписчиков: {total_subscribers}\nКоличество пользователей, ожидающих подтверждения подписки: {total_users_waiting_confirmation}",
    "server": "Сервер🖥\n\nВыберите действие:",
    "check_health": "Проверка работоспособности сервера",
    "check_health_success": "✅ Сервер работает!\n\nСтатус: {status}\nСервис: {service}",
    "check_health_error": "❌ Сервер недоступен\n\nКод ответа: {status}",
    "stop_all_trading_success": "✅ Вся торговля остановлена\n\n{message}",
    "stop_all_trading_error": "❌ Ошибка остановки всей торговли\n\n{error}",
    "wait_confirm": "Ожидающие подтверждения🕒\n\nВыберите метод поиска пользователей",
    "search_by_username_id": "Введите username или ID пользователя",
    "search_subscribers_by_username_id": "Введите username или ID подписчика",
    "user_not_search": "Пользователь не найден 🚫",
    "user_not_wait_confirm": "Пользователь не ожидает подтверждения 🚫",
    "user_not_subscriber": "Пользователь не является подписчиком 🚫",
    "wait_confirm_list_title": "Ожидают подтверждения подписки\n\nСтр. {page} из {pages} · всего {total}",
    "wait_confirm_list_empty": "Никто не ожидает подтверждения.",
    "subscribers_list_title": "Подписчики\n\nСтр. {page} из {pages} · всего {total}",
    "subscribers_list_empty": "Подписчиков нет.",
    "user_info": "Имя: {name}\nТГ ID: {tg_id}\nЯзык: {language}\n\nСостояние подписки: {subscription_status}\nТекущая стоимость подписки: {current_amount}\nТип подписки: {subscription_type}\nДата оплаты: {payment_date}\nДата окончания: {end_subscription_date}",
    "subscribers": "Подписчики👥\n\nВыберите метод поиска подписчиков",
    "subscribers_main_info": "Имя: {name}\nТГ ID: {tg_id}\nЯзык: {language}",
    "subscription_settings": "⚙️ Настройки подписки:\n\nСостояние подписки: {subscription_status}\nТекущая стоимость подписки: {current_amount}\nВсего выплачено за подписки: {total_amount}\nТип подписки: {subscription_type}\nДата оплаты: {payment_date}\nДата окончания: {end_subscription_date}",
    "edit_date_end_subs": "Введите дату в формате 'yyyy.mm.dd. hh.mm.ss'",
    "edit_date_end_subs_invalid_format": "Неверный формат даты. Используйте: yyyy.mm.dd. hh.mm.ss",
    "edit_date_end_subs_success": "Дата окончания подписки обновлена: {end_subscription_date}",
    "bybit_settings": "⚙️ Настройки клиента ByBit:\n\nAPI ключ: {api_key}\nAPI секрет: {api_secret}\nСумма для открытия сделки: {sum_for_trades}\nОстановлен трейдинг: {stop_trading} ",
    "edit_api_key": "Введите новый API ключ",
    "edit_api_secret": "Введите новый API secret",
    "edit_sum_for_trades": "Введите новую сумму сделки",
    "edit_api_key_success": "API ключ обновлён.",
    "edit_api_secret_success": "API secret обновлён.",
    "edit_sum_for_trades_success": "Сумма сделки обновлена: {sum_for_trades}",
    "statistics_info": "📊 Статистика подписчика: \n\nОбщее количество сделок: {total_trades}\nОбщий PnL: {total_pnl}\nКоличество + сделок: {positive_trades}\nЗаработанная суммка с + сделок: {sum_positive_trades}\n Количество - сделок: {negative_trades}\nПроигранная сумма с - сделок: {sum_negative_trades}",
    "error_search_user": "Сначала найдите пользователя. 🚫",
    "error_user_not_found": "Пользователь не найден в БД. 🚫",
  }, # -------------------------------------------------------------
  "admin_btn": {
    "users_list": "Пользователи 👥",
    "statistics_project": "Статистика 📊",
    "stop_all_trading": "🛑 Остановить всю торговлю",
    "server": "Сервер 🖥",
    "check_health": "Проверка работоспособности сервера",
    "wait_confirm": "Ожидающие подтверждения",
    "subscribers": "Подписчики",
    "wait_confirm_list": "Список пользователей",
    "subscribers_list": "Список подписчиков",
    "search_by_username_id": "Поиск по username & ID",
    "proccess_search_wair_confirm": "Продолжить поиск",
    "back_menu_wait_confirm": "Вернуться в меню",
    "confirm_subscription": "Подтвердить подписку",
    "cancel_subscription": "Отклонить запрос",
    "prolong_subscription": "Продлить подписку",
    "cancel_prolong_subscription": "Отклонить продление подписки",
    "subscription_settings": "Настройки подписки ⚙️",
    "edit_subscription_true_mode": "Включить подписку",
    "edit_subscription_false_mode": "Выключить подписку",
    "edit_date_end_subs": "Изменить дату окончания подписки",
    "bybit_settings": "Настройки Bybit ⚙️",
    "edit_api_key": "Изменить API ключ",
    "edit_api_secret": "Изменить API secret",
    "edit_sum_for_trades": "Изменить сумму сделки",
    "edit_stop_trades": "Остановить/Продолжить торговлю",
    "edit_stop_trading_stop_mode": "Остановить торговлю",
    "edit_stop_trading_resume_mode": "Продолжить торговлю",
    "statistics_info": "Статистика 📊",
    "trading_list": "Список сделок",
    "list_prev_page": "◀️ Пред.",
    "list_next_page": "След. ▶️",
    "back_to_user_list": "К списку",
  }, # -------------------------------------------------------------
  "general": {
    "back": "⬅️ Назад",
    "admin_to_main_menu": "Главное меню",
  }
}