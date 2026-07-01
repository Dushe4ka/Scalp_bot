from config import URL_PAYMENT, SUBSCRIPTION_PRICE_USD

RU_CONFIGURATION = {
  "start_text": {
    "greeting": "Здравствуйте! Я ZdormanBot 👋",
    "greeting_help": "Помогу оформить подписку и настроить торговлю на Bybit.",
    "greeting_help_first": "Давайте помогу оформить подписку и настроить торговлю на Bybit.",
    "quick_start": "📋 Быстрый старт:\n1. Оплатите подписку\n2. Дождитесь подтверждения (до 24 ч)\n3. Укажите API-ключ Bybit\n4. Укажите сумму сделки\n5. Готово — алгоритм работает автоматически",
    "choose_language": "Выберите язык / Choose language:",
    "welcome_intro": (
        "Преимущества торгового бота:\n"
        "⚡️ Скорость входа в сделку — около 1 секунды после получения сигнала.\n"
        "⚡️ Работает полностью автоматически на 1-минутном таймфрейме.\n"
        "⚡️ Сам рассчитывает рекомендуемую сумму входа в позицию.\n"
        "⚡️ Автоматически выставляет всю сетку ордеров на продажу.\n"
        "⚡️ Использует скользящий Take Profit для максимизации прибыли.\n"
        "⚡️ Не требует подписки TradingView для получения уведомлений.\n"
        "⚡️ Все сообщения о входах, выходах и работе системы приходят прямо в Telegram.\n"
        "⚡️ При соблюдении рекомендуемых настроек риск полной ликвидации сведен к минимуму.\n\n"
        "Особенности:\n"
        "• Работает только на бирже Bybit.\n"
        "• Предназначен исключительно для торговли на 1-минутном таймфрейме."
    ),
  },
  "start_btn": {
    "url_tg": "📢 Наш Telegram-канал",
    "personal_account": "👤 Личный кабинет",
    "onboarding_progress": "📋 Прогресс подключения",
    "onboarding_setup": "⚙️ Настройка подключения",
    "subscription_buy": "💳 Оформить подписку",
    "prolong_subscription": "🔄 Продлить подписку",
  }, # -------------------------------------------------------------
  "subscription_text": {
    "buy_info": (
        f"💳 Оплата подписки — 1 месяц = {SUBSCRIPTION_PRICE_USD}$\n\n"
        f"1️⃣ Переведите {SUBSCRIPTION_PRICE_USD}$ на кошелёк:\n{URL_PAYMENT}\n"
        "   Сеть: TRC-20 (только с биржевого аккаунта)\n"
        "2️⃣ Нажмите «✅ Я оплатил»\n"
        "3️⃣ Введите ID платежа и подтвердите\n"
        "4️⃣ Дождитесь активации администратором (до 24 ч)\n\n"
        "После оплаты можно заранее настроить API-ключ в личном кабинете."
    ),
    "question": (
        "📋 Инструкция после оплаты:\n\n"
        "1. Нажмите «✅ Я оплатил»\n"
        "2. Введите ID платежа из истории перевода\n"
        "3. Подтвердите отправку\n"
        "4. Администратор проверит платёж в течение 24 часов\n"
        "5. После активации настройте API-ключ и сумму сделки в личном кабинете"
    ),
    "prolong_question": (
        "📋 Инструкция после оплаты продления:\n\n"
        "1. Нажмите «✅ Я оплатил»\n"
        "2. Введите ID платежа\n"
        "3. Подтвердите отправку\n"
        "4. Администратор продлит подписку в течение 24 часов"
    ),
    "paid": "Отлично! Нажмите «Ввести ID платежа» и отправьте ID перевода в чат.\n\nАдминистратор проверит платёж в течение 24 часов.",
    "prolong_paid": "Отлично! Нажмите «Ввести ID платежа» и отправьте ID перевода в чат.\n\nАдминистратор продлит подписку в течение 24 часов.",
    "input_payment_id": "✏️ Введите ID платежа в поле сообщения ниже и отправьте его в этот чат.",
    "confirm_payment": "Все верно: {payment_id}",
    "confirm_payment_success": "Спасибо! Заявка отправлена.\n\nАдминистратор проверит платёж в течение 24 часов. Пока ждёте — можете настроить API-ключ Bybit в личном кабинете.",
    "prolong_confirm_payment_success": "Спасибо! Заявка на продление отправлена.\n\nАдминистратор проверит платёж в течение 24 часов.",
    "prolong_subscription": (
        f"🔄 Продление подписки\n\n"
        f"1️⃣ Переведите {SUBSCRIPTION_PRICE_USD}$ на кошелёк:\n{URL_PAYMENT}\n"
        "   Сеть: TRC-20\n"
        "2️⃣ Нажмите «✅ Я оплатил»\n"
        "3️⃣ Введите ID платежа и подтвердите"
    ),
    "payment_confirmed": "✅ Ваша оплата подтверждена! Подписка активирована.",
    "payment_rejected": "❌ Оплата не подтверждена. Если у вас есть вопросы — обратитесь в техподдержку.",
    "prolong_confirmed": "✅ Продление подписки подтверждено!",
    "prolong_rejected": "❌ Продление подписки отклонено. Если у вас есть вопросы — обратитесь в техподдержку.",
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
    "paid": "✅ Я оплатил",
    "question": "📋 Инструкция по оплате",
    "input_payment_id": "📝 Ввести ID платежа",
    "confirm_payment": "✅ Всё верно",
    "reject_payment": "✏️ Исправить ID",
  }, # -------------------------------------------------------------
  "profile_text": {
    "profile_menu": "Мой профиль 👤\n\nДата подписки: {payment_date}\nТип: {subscription_type}\nСумма на сделку: {sum_for_trades} USDT\nAPI-ключ Bybit: {api_key}\n{api_key_expiry_line}\n\n{onboarding_checklist}",
    "profile_menu_without_subscription": (
        "Подключение к сервису 🚀\n\n"
        "Здесь — ваш прогресс и следующие шаги.\n"
        "Полный личный кабинет (настройки, торговля, статистика) откроется после активации подписки.\n\n"
        "{onboarding_checklist}\n\n"
        "👇 Начните с оформления подписки"
    ),
    "profile_menu_wait_sub_confirmation": (
        "Подключение к сервису 🚀\n\n"
        "🎉 Оплата отправлена на проверку\n"
        "🕒 Ожидание подтверждения (до 24 ч)\n\n"
        "{onboarding_checklist}\n\n"
        "💡 Пока ждёте — можно заранее настроить API-ключ в разделе ниже"
    ),
    "profile_statistics": "📊 Статистика \n\nОбщее количество сделок: {total_trades}\nОбщий PnL: {total_pnl}\nКоличество + сделок: {positive_trades}\nЗаработанная суммка с + сделок: {sum_positive_trades}\n Количество - сделок: {negative_trades}\nПроигранная сумма с - сделок: {sum_negative_trades}",
    "profile_settings": "⚙️ Настройки\n\n🔑 API-ключ: {api_key}\n🔐 Секретный ключ: {api_secret}\n💵 Сумма на сделку: {sum_for_trades} USDT\n{api_key_expiry_line}\n\n{settings_hint}",
    "settings_hint_api_first": "Сначала укажите API-ключ Bybit — после этого станет доступна настройка суммы сделки.",
    "settings_hint_ready": "Настройте API-ключ и сумму сделки — без этого алгоритм не сможет торговать.",
    "settings_hint_sum": "Укажите сумму сделки — это последний шаг перед началом торговли.",
    "onboarding_checklist_title": "📋 Ваш прогресс:",
    "onboarding_step_subscription": "Оплата подписки отправлена",
    "onboarding_step_wait_confirm": "Подписка активирована администратором",
    "onboarding_step_api": "API-ключ Bybit указан",
    "onboarding_step_sum": "Сумма сделки указана",
    "onboarding_step_ready": "Всё готово к торговле",
    "onboarding_wait_confirm_hint": "💡 Пока ждёте подтверждения, можете заранее указать API-ключ в настройках.",
    "onboarding_all_done_hint": "✅ Настройка завершена. Сделки открываются автоматически по сигналу сервиса.",
    "feature_locked_wait_confirm": "⏳ Раздел будет доступен после подтверждения подписки администратором (до 24 ч).",
    "validation_sum_positive": "Сумма сделки должна быть больше 0.",
    "validation_enter_number": "Введите число, например: 25 или 25.5",
    "trading_menu": "📈 Торговля\n\nСделки открываются автоматически по сигналу сервиса. Здесь вы можете посмотреть активные позиции и остановить торговлю при необходимости.\n\nВыберите действие:",
    "profile_settings_api_key": (
        "🔑 Шаг 1 из 2 — API key\n\n"
        "Введите API key из Bybit (личный кабинет → API Management).\n"
        "Сейчас бот подключается к: {account_mode}."
    ),
    "profile_settings_api_secret": (
        "🔐 Шаг 2 из 2 — API secret\n\n"
        "Введите secret для ключа {api_key_preview}.\n\n"
        "Secret показывается только при создании ключа. "
        "Если потеряли — создайте новый ключ в Bybit и начните с шага 1."
    ),
    "profile_settings_api_saved_prompt_sum": "✅ API-ключ сохранён. Теперь укажите сумму сделки:",
    "profile_settings_api_invalid": (
        "❌ Bybit не принял пару key + secret.\n\n"
        "Чаще всего причина в одном из пунктов:\n"
        "• опечатка в key или secret;\n"
        "• ключ создан для другого режима (нужен {account_mode});\n"
        "• у ключа нет прав Read на Unified / Futures.\n\n"
        "Начнём заново — сначала снова введите API key:"
    ),
    "api_key_instruction_caption": "📹 Инструкция: как создать API ключ на Bybit.\n\nПосле просмотра нажмите «Ввести API ключ».",
    "profile_settings_sum_for_trades": "Введите сумму сделки\n\nРекомендуемая сумма: {recommended_usdt} USDT",
    "profile_settings_sum_for_trades_limited": (
        "Введите сумму сделки\n\n"
        "Сумма не выше: {max_usdt} USDT\n"
        "({percent}% от баланса futures-счёта)\n\n"
        "Это правило сервиса помогает защитить ваш депозит: при усреднениях и стопах алгоритм использует несколько ордеров, "
        "и завышенная сумма сделки резко увеличивает риск просадки."
    ),
    "profile_settings_sum_for_trades_api_required": (
        "Чтобы рассчитать допустимую сумму сделки, сначала укажите API ключ и secret в настройках профиля.\n\n"
        "После сохранения ключей вернитесь сюда — мы покажем максимальную сумму по правилам сервиса."
    ),
    "profile_settings_sum_for_trades_balance_zero": (
        "Не удалось рассчитать лимит: на futures-счёте нулевой баланс или ключ не даёт доступ к балансу.\n\n"
        "Пополните счёт на Bybit и проверьте права API-ключа, затем повторите."
    ),
    "profile_settings_sum_for_trades_exceeds_limit": (
        "Сумма {entered_sum} USDT превышает допустимый предел.\n\n"
        "По правилам проекта максимальная сумма сделки — {max_usdt} USDT ({percent}% от вашего баланса). "
        "Это ограничение действует для безопасности ваших сделок: оно снижает нагрузку на депозит при серии усреднений.\n\n"
        "Пожалуйста, введите сумму не выше {max_usdt} USDT."
    ),
    "profile_settings_sum_for_trades_risk_warning": "⚠️ Вы уверены?\n\nВы ввели: {entered_sum} USDT\nРекомендуемая сумма: {recommended_usdt} USDT\n\nВыставленное значение ведёт к повышенным рискам при работе алгоритма.",
    "profile_balance": "💰 Баланс futures аккаунта: {balance} USDT",
    "profile_balance_api_missing": "❌ Не удалось получить баланс: в настройках профиля не указаны API key/secret.",
    "profile_balance_error": "❌ Не удалось получить баланс. Попробуйте позже.",
    "profile_history_trades_title": "📋 История сделок (последние {count})",
    "profile_history_trades_page": "Стр. {page}/{pages} · всего {total}",
    "profile_history_trades_empty": "📋 История сделок пуста.",
    "profile_history_trades_error": "❌ Не удалось получить историю сделок. Попробуйте позже.",
    "profile_history_trade_details_title": "📄 Сделка",
    "trade_state_active": "активна",
    "trade_state_closed": "закрыта",
    "trade_details_symbol": "📊 Символ: {value}",
    "trade_details_state": "🏷️ Состояние: {value}",
    "trade_details_entry": "💰 Вход: {value}",
    "trade_details_entry_active": "💰 Цена входа: {value}",
    "trade_details_exit": "💸 Выход: {value}",
    "trade_details_size": "📦 Размер: {value}",
    "trade_details_pnl": "💵 PnL: {value}",
    "trade_details_open": "🕒 Открыта: {value}",
    "trade_details_close": "🕒 Закрыта: {value}",
    "trade_details_created": "🗂️ Добавлено: {value}",
    "trade_history_pnl": "PnL: {value}",
    "active_trades_page_title": "🟢 Активные сделки\nСтр. {page}/{pages} · всего {total}",
    "active_trades_empty": "🟢 Активных сделок нет.",
    "active_trades_error": "❌ Не удалось получить активные сделки. Попробуйте позже.",
    "active_trade_details_title": "📄 Активная сделка",
    "active_trade_not_found": "❌ Не удалось получить данные по активной сделке {symbol}.",
    "active_trade_stop_success": "🛑 Торговля по {symbol} остановлена.\n{message}",
    "active_trade_stop_error": "❌ Не удалось остановить торговлю по {symbol}.",
    "stop_all_trading_success": "🛑 Вся торговля остановлена.\n{message}",
    "stop_all_trading_error": "❌ Не удалось остановить всю торговлю.",
    "profile_api_key_expiry": "🔑 API ключ активен ещё {days_left} дн. (до {expiry_date})",
    "api_key_reminder_3d": (
        "⚠️ Внимание!\n\n"
        "Через 3 дня ({expiry_date}) истечёт срок действия вашего API-ключа Bybit.\n"
        "Создайте новый ключ и обновите его в настройках бота."
    ),
    "api_key_reminder_1d": (
        "⚠️ Внимание!\n\n"
        "Через 1 день ({expiry_date}) истечёт срок действия вашего API-ключа Bybit.\n"
        "Создайте новый ключ и обновите его в настройках бота."
    ),
    "api_key_expired_today": (
        "❌ Сегодня ({expiry_date}) истекает срок действия вашего API-ключа Bybit.\n"
        "Создайте новый ключ и обновите его в настройках бота, иначе торговля перестанет работать."
    ),
  },
  "profile_btn": {
    "subscription_buy": "💳 Оформить подписку",
    "tech_support": "💬 Техподдержка",
    "statistics": "📊 Статистика",
    "settings_profile": "⚙️ Настройки",
    "setup_profile_early": "⚙️ Настроить API заранее",
    "go_to_settings": "⚙️ Перейти в настройки",
    "edit_api_key_secret": "🔑 API-ключ Bybit",
    "api_key_instruction_enter": "🔑 Ввести API-ключ",
    "edit_sum_for_trades": "💵 Сумма сделки",
    "edit_sum_for_trades_locked": "💵 Сумма (сначала API-ключ)",
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
    "admin_menu": (
        "Админ-панель 👨‍💻\n\n"
        "📋 Разделы:\n"
        "• Пользователи — подтверждение оплат и управление подписчиками\n"
        "• Статистика — сводка по проекту\n"
        "• Остановка торговли — экстренная остановка для всех\n"
        "• Сервер — проверка API сервера\n\n"
        "Выберите действие:"
    ),
    "users_list": (
        "👥 Пользователи\n\n"
        "• Ожидающие подтверждения — новые заявки на оплату\n"
        "• Подписчики — активные клиенты с доступом к алгоритму\n\n"
        "Выберите раздел:"
    ),
    "statistics_project": "📊 Статистика проекта\n\nВсего пользователей: {total_users}\nПодписчиков: {total_subscribers}\nОжидают подтверждения: {total_users_waiting_confirmation}",
    "server": "🖥 Сервер\n\nПроверка доступности API сервера алгоритма.",
    "check_health": "Проверка работоспособности сервера",
    "check_health_success": "✅ Сервер работает!\n\nСтатус: {status}\nСервис: {service}",
    "check_health_error": "❌ Сервер недоступен\n\nКод ответа: {status}",
    "stop_all_trading_success": "✅ Вся торговля остановлена\n\n{message}",
    "stop_all_trading_error": "❌ Ошибка остановки всей торговли\n\n{error}",
    "stop_all_trading_done": "Массовая остановка завершена",
    "stop_all_trading_report": (
        "👥 Проверено пользователей: {processed}\n"
        "✅ Успешно остановлено: {stopped}\n"
        "⏭️ Пропущено (нет API ключей): {skipped}\n"
        "❌ Ошибок: {errors}"
    ),
    "wait_confirm": (
        "🕒 Ожидающие подтверждения\n\n"
        "• Список — все заявки с пагинацией\n"
        "• Поиск — найти по username или Telegram ID\n\n"
        "Выберите способ:"
    ),
    "search_by_username_id": "🔍 Введите username или Telegram ID пользователя",
    "search_subscribers_by_username_id": "🔍 Введите username или Telegram ID подписчика",
    "user_not_search": "Пользователь не найден 🚫",
    "user_not_wait_confirm": "Пользователь не ожидает подтверждения 🚫",
    "user_not_subscriber": "Пользователь не является подписчиком 🚫",
    "user_not_confirmed_payment_bot": "ℹ️ Пользователь ещё не подтвердил оплату в боте (не нажал «✅ Всё верно»).",
    "wait_confirm_list_title": "Ожидают подтверждения подписки\n\nСтр. {page} из {pages} · всего {total}",
    "wait_confirm_list_empty": "Никто не ожидает подтверждения.",
    "subscribers_list_title": "Подписчики\n\nСтр. {page} из {pages} · всего {total}",
    "subscribers_list_empty": "Подписчиков нет.",
    "user_info": "👤 Карточка пользователя\n\nИмя: {name}\nТГ ID: {tg_id}\nЯзык: {language}\n\nСостояние подписки: {subscription_status}\nТекущая стоимость: {current_amount}\nТип: {subscription_type}\nДата оплаты: {payment_date}\nДата окончания: {end_subscription_date}",
    "subscribers": (
        "👥 Подписчики\n\n"
        "• Список — все подписчики с пагинацией\n"
        "• Поиск — найти по username или Telegram ID\n\n"
        "Выберите способ:"
    ),
    "subscribers_main_info": "👤 Карточка подписчика\n\nИмя: {name}\nТГ ID: {tg_id}\nЯзык: {language}\nЛимит суммы сделки: {trade_amount_limit_status}",
    "subscription_settings": "⚙️ Настройки подписки\n\nСостояние: {subscription_status}\nТекущая стоимость: {current_amount}\nВсего выплачено: {total_amount}\nТип: {subscription_type}\nДата оплаты: {payment_date}\nДата окончания: {end_subscription_date}",
    "edit_date_end_subs": "Введите дату в формате 'yyyy.mm.dd. hh.mm.ss'",
    "edit_date_end_subs_invalid_format": "Неверный формат даты. Используйте: yyyy.mm.dd. hh.mm.ss",
    "edit_date_end_subs_success": "Дата окончания подписки обновлена: {end_subscription_date}",
    "bybit_settings": "⚙️ Настройки Bybit\n\nAPI ключ: {api_key}\nAPI секрет: {api_secret}\nСумма сделки: {sum_for_trades}\nТорговля остановлена: {stop_trading}",
    "edit_api_key": "Введите новый API ключ",
    "edit_api_secret": "Введите новый API secret",
    "edit_sum_for_trades": "Введите новую сумму сделки",
    "edit_api_key_success": "API ключ обновлён.",
    "edit_api_secret_success": "API secret обновлён.",
    "edit_sum_for_trades_success": "Сумма сделки обновлена: {sum_for_trades}",
    "statistics_info": "📊 Статистика подписчика\n\nВсего сделок: {total_trades}\nОбщий PnL: {total_pnl}\nПрибыльных: {positive_trades} (+{sum_positive_trades})\nУбыточных: {negative_trades} (-{sum_negative_trades})",
    "subscription_status_active": "Активна",
    "subscription_status_inactive": "Не активна",
    "stop_trading_yes": "Да",
    "stop_trading_no": "Нет",
    "access_denied": "Доступ запрещён",
    "action_failed": "Не удалось выполнить действие: {error}",
    "error_search_user": "Сначала найдите пользователя. 🚫",
    "error_user_not_found": "Пользователь не найден в БД. 🚫",
    "trade_amount_limit_unlimited": "отключён (расширенный режим)",
    "trade_amount_limit_standard": "стандартный (по правилам сервиса)",
    "toggle_unlimited_trade_added": "Пользователю разрешена установка суммы выше лимита",
    "toggle_unlimited_trade_removed": "Для пользователя снова действует лимит суммы сделки",
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
    "proccess_search_wair_confirm": "🔍 Искать снова",
    "back_to_wait_confirm_menu": "⬅️ К ожидающим",
    "back_to_subscribers_menu": "⬅️ К подписчикам",
    "search_subscribers_again": "🔍 Искать снова",
    "back_to_subscriber_card": "⬅️ К карточке пользователя",
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
    "toggle_unlimited_trade_add": "🔓 Разрешить сумму без лимита",
    "toggle_unlimited_trade_remove": "🔒 Вернуть лимит суммы",
  }, # -------------------------------------------------------------
  "general": {
    "back": "⬅️ Назад",
    "main_menu": "🏠 Главное меню",
    "change_language": "🌐 Сменить язык",
    "admin_to_main_menu": "🏠 Выйти в главное меню",
    "admin_panel": "👨‍💻 Админ-панель",
    "help_title": "❓ Справка по боту",
    "help_setup": (
        "📋 Порядок действий:\n"
        "1. Оформите подписку\n"
        "2. Дождитесь подтверждения (до 24 ч)\n"
        "3. Укажите API-ключ Bybit в настройках\n"
        "4. Укажите сумму сделки\n\n"
        "Сделки открываются автоматически по сигналу сервиса — запускать вручную не нужно."
    ),
    "help_commands": (
        "Команды:\n"
        "/start или /main_menu — главное меню\n"
        "/profile — личный кабинет\n"
        "/help — эта справка"
    ),
  }
}