---
title: Бесплатный пробный период (7 дней)
date: 2026-08-11
status: approved
---

# Бесплатный пробный период

## Проблема

Новым пользователям нужен способ попробовать бота с полным доступом (как при активной подписке),
без оплаты, на ограниченный срок — **1 неделю**. Требования:

- полный доступ, как при подписке (торговля, статистика, история);
- ровно один раз на пользователя, без возможности повторного триала;
- не должно ломать существующую логику подписки/торговли;
- нужно решить, разделять ли пользователей с подпиской и с триалом на «отдельные потоки»;
- изменения в боте должны быть понятны и user-friendly.

## Ключевая находка (определяет архитектуру)

Гейт торговли (`database/users_repository.py::list_trading_candidates`) и периодическая проверка
(`celery_app/subscription_lifecycle_service.py::run_subscription_lifecycle_check` через
`database/subscription_lifecycle_repository.py::list_active_subscriptions`/`deactivate_subscription`)
фильтруют пользователей **только** по `subscription_data.subscription: True` +
`subscription_data.end_subscription_date` — полностью не зная о значении
`subscription_data.subscription_type`.

Поле `subscription_type` уже существует в схеме (`_default_document`) и уже отображается в
профиле и админ-карточке (`"Тип: {subscription_type}"`), сейчас туда всегда пишется `"1 мес"`.

**Вывод:** триал не требует ни отдельной коллекции, ни изменений в гейте торговли или в
Celery Beat проверке подписок — они уже работают одинаково для любого `subscription_type`.
«Разделение потоков» реализуется как **различие в UI/текстах**, а не как отдельная модель данных —
это исключает риск рассинхрона (например, триал-пользователь не попадёт в очередь на торговлю,
если завести отдельный гейт).

## Решение

### Модель данных

Внутри существующего `subscription_data` (без новой коллекции):

- `subscription_type = "trial"` вместо `"1 мес"` — переиспользует поле и весь UI, который его уже
  показывает.
- Новый флаг `subscription_data.trial_used: bool` (по умолчанию `False` в `_default_document`) —
  разовость триала.
- `subscription = True`, `payment_date = now`, `end_subscription_date = now + 7 дней` — как у
  обычной подписки, гейт торговли и лайфцикл-проверка работают без изменений.

### Новый метод репозитория

`database/users_repository.py::start_trial_period(tg_id: int) -> bool`

- Атомарное `find_one_and_update` с условием `subscription_data.trial_used != True` **в фильтре**
  запроса (не read-then-write) — защита от гонки при двойном тапе/повторном вызове, а не только
  скрытие кнопки в UI.
- При успехе: `subscription=True`, `subscription_type="trial"`, `trial_used=True`,
  `payment_date=now`, `end_subscription_date=now+timedelta(days=7)`.
- Возвращает `False`, если триал уже был использован — вызывающий код (бот/админка) показывает
  соответствующее сообщение вместо активации.

При истечении переиспользуется существующий `deactivate_subscription()` **как есть** — он снимает
`subscription`/`wait_sub_confirmation`, не трогает `subscription_type` (то же поведение и для
обычной подписки, менять не нужно).

### Точки входа в боте

Обе — под общей проверкой доступности триала
(`is_subscriber == False and wait_sub_confirmation == False and trial_used == False`) — третье
условие важно для главного меню: там кнопка «Оформить подписку» уже скрывается на время ожидания
подтверждения оплаты (`elif not wait_confirm` в `build_main_menu_keyboard`), кнопка триала должна
вести себя так же, иначе пользователю с pending-оплатой предложат ещё и триал:

1. **Главное меню `/start`** (`bot/utils/main_menu.py::build_main_menu_keyboard`) — новая кнопка
   рядом с существующей `subscription_buy`.
2. **Профиль без подписки** (`bot/keyboards/inline_kb.py::profile_menu_kb_without_subscription`) —
   аналогично, рядом с «Оформить подписку».

Обе точки используют один и тот же helper проверки доступности (избегаем дублирования условия).

**UX активации:** по тапу — экран-подтверждение («Активировать пробный период на 7 дней бесплатно?»
→ `[Да, активировать]` / `[Отмена]`), а не мгновенная активация в один тап — защита от случайного
расходования единственного триала. После успешной активации кнопка триала пропадает из обоих мест
(флаг `trial_used=True`).

### Уведомления (напоминания/истечение)

Отдельные текстовые ключи — не переиспользуем `subscription_reminder_*` дословно, чтобы
пользователь понимал разницу между «истекает подписка» и «истекает бесплатный период»:

- `trial_reminder_3d`, `trial_reminder_1d`, `trial_expired` — в `bot/languages/ru.py` и `en.py`.
- Пример (ru): `"⏳ Ваш бесплатный пробный период завершается через 3 дня — оформите подписку,
  чтобы не потерять доступ"`.

В `celery_app/subscription_lifecycle_service.py::run_subscription_lifecycle_check` — выбор ключа
шаблона по `sub.get("subscription_type") == "trial"` вместо жёстко заданного
`"subscription_reminder_*"`. Остальная логика (idempotency-флаги `notify_3d_for_end`/`notify_1d_for_end`/
`notify_expired_for_end`, расписание Celery Beat, часовой пояс) — без изменений, полностью общая
для подписки и триала.

### Админка — ручной контроль (для техподдержки)

В карточке подписчика — новые callback-классы в `bot/callback_data/admin_lists.py`, по тому же
паттерну, что `AdminConfirmSubscriptionCb`/`AdminCancelSubscriptionCb`:

- `AdminGrantTrialCb(tg_id)` — «Выдать триал вручную», вызывает тот же `start_trial_period()`.
- `AdminResetTrialCb(tg_id)` — «Сбросить флаг использования» (`trial_used=False`) — на случай
  обращения в техподдержку с просьбой о повторном триале.

### Что сознательно не меняется

- `admin_check_subscription` / `admin_prolong_subscription` / `prolong_end_subscription_date` —
  не участвуют в триале, это чисто admin-driven поток подтверждения **платной** подписки.
- Продления триала нет — он одноразовый; после истечения доступен только обычный платный поток.
- Гейт `/short_3_limit` (`list_trading_candidates`) — без изменений.
- `deactivate_subscription()` — без изменений, уже универсален для любого `subscription_type`.

### Тестирование

- Unit: `start_trial_period` — успешная выдача первый раз; `False` при повторном вызове (включая
  параллельный вызов — проверка атомарности условия в фильтре update).
- Unit: выбор текстового ключа (`trial_*` vs `subscription_*`) в `run_subscription_lifecycle_check`
  по `subscription_type`.
- Manual: полный путь — активация триала в боте → проверка появления в `list_trading_candidates` →
  ручной прогон `check_subscription_lifecycle` за 3 дня/1 день/после истечения (подмена
  `end_subscription_date` в тестовом документе) → проверка текста уведомлений и автоотключения.
- Manual: повторный тап по кнопке триала после активации — кнопка должна отсутствовать; прямой
  вызов `start_trial_period` для уже использовавшего — `False`.
