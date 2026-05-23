# MVP multiuser: multi-day прогон BTCUSDT — закрытие и некорректная статистика

Анализ логов **21.05.2026 ~11:13** → **22.05.2026 ~22:30** (активная торговля ~**35 ч**), feed остановлен **22.05 22:30**, процесс feed — **23.05 18:09**.

Два пользователя, один сигнал, Phase 2, Bybit Demo.

| tg_id | Имя | Engine | Сумма в профиле |
|-------|-----|--------|-----------------|
| `1395854084` | Dushe4kaaa | 0 | 100 USDT |
| `5032415442` | SHIFYuu | 1 | 150 USDT |

Предыдущий обзор старта: [demo_btcusdt_12h_log_analysis.md](./demo_btcusdt_12h_log_analysis.md).

---

## 1. Хронология (по логам)

| Время | Событие |
|-------|---------|
| 21.05 ~11:13 | `POST /short_3_limit` BTCUSDT, `queued=2`, WS feed открыт |
| 21.05–22.05 | Непрерывный цикл PnL, feed failover primary↔backup |
| 22.05 00:12–06:15 | Периодические `Failover: primary -> backup` и обратно (T11) |
| 22.05 ~22:29 | PnL ~**+2.3–2.9%**, цена BTC ~76100–76200 |
| 22.05 **22:30:50** | **+3.01%** — срабатывание БУ/SL + **трейлинг стоп** на ~75709.4 (оба engine) |
| 22.05 **22:30:51–53** | `stop_trading` — отмена 3 limit-ордеров, **«Нет открытой позиции»** |
| 22.05 **22:30:53–54** | `send_notification_to_user` → оба tg_id (T14 router) |
| 22.05 **22:30:54** | Feed: `Stopped WS streams for idle symbol BTCUSDT` |
| 23.05 18:09 | Feed process: `DualMarketFeed stopped` (ручной Ctrl+C) |

---

## 2. Закрытие сделки (engine 0 и 1, зеркально)

### 2.1 Последние тики перед выходом

**Engine 0 — `1395854084` (T12):**

```text
📊 [1395854084:BTCUSDT] 75709.4 | +3.01% | +28.19 USDT
Попытка установки стоп-лосса … 75709.4
🟢 Трейлинг стоп активирован для BTCUSDT на цене 75709.4
```

**Engine 1 — `5032415442` (T13):**

```text
📊 [5032415442:BTCUSDT] 75709.4 | +3.01% | +44.64 USDT
… (те же SL + trailing)
```

**Вывод:** алгоритм отработал до порога **`TRIGGER_PERCENTAGE=3`** (~3% движения в пользу шорта), включил защиту и трейлинг. Реальный PnL в момент закрытия по логам: **~+28 USDT** и **~+44 USDT**, не 0.

### 2.2 `stop_trading` после закрытия позиции

```text
1. Отменяем все открытые ордера … ✅ 3 limit Sell отменены
2. Закрываем позицию … Нет открытой позиции для BTCUSDT
✅ Остановка торговли для BTCUSDT завершена!
```

Позиция уже закрыта **биржей** (трейлинг/SL), engine лишь подчистил лимитки. Это штатно, не ошибка торговли.

### 2.3 Refcount feed

```text
Released feed WS for BTCUSDT
Last session closed for BTCUSDT — feed WS release requested
```

После закрытия **обеих** сессий feed корректно запросил release → **22:30:54** idle stop WS (T11).

---

## 3. Уведомления Telegram

### 3.1 Router (T14) — доставка OK

```text
Task send_notification_to_user … tg_id=5032415442 … succeeded
Task send_notification_to_user … tg_id=1395854084 … succeeded
```

Личные сообщения **ушли обоим** (после правки multiuser-notify). Канал доставки работает.

### 3.2 Текст в боте — некорректный

Оба пользователя получили:

```text
🔄 Позиция закрыта
💰 Цена входа: 0
💸 Цена выхода: 0
💵 Финальный PnL: +0.00 USDT
```

При этом в логах engine за секунду до закрытия: **+28 USDT** / **+44 USDT**.

---

## 4. Причина нулевой статистики в сообщении (по логам)

### 4.1 Цепочка в коде

При `current_size == 0`:

1. `_check_position_once` → `_persist_closed_trade()`
2. `get_result_position_info` → Bybit `get_last_position_info`
3. `insert_closed_trade` → Mongo `history_trades`
4. `apply_user_statistics_delta` → `$inc` по `users.statistics.*`
5. Текст уведомления берётся из **`closed_info`** = результат `_persist_closed_trade`

### 4.2 Ошибка Mongo (engine 0, T12) — **корневая причина**

```text
history_trades_repository - ERROR - apply_user_statistics_delta:
Cannot apply $inc to a value of non-numeric type.
… field 'sum_positive_trades' of non-numeric type string

short_bu_ts_limit_engine - ERROR - ❌ Ошибка сохранения history_trades/statistics
```

У пользователя в Mongo поле **`statistics.sum_positive_trades` хранится как строка**, а не число. `$inc` падает → **весь** `_persist_closed_trade` ловит exception и возвращает **`None`**.

### 4.3 Следствие для уведомления

```python
closed = await self._persist_closed_trade()  # → None
closed_info = closed or {}                   # → {}
# entry_price, exit_price, pnl_usdt → 0.0
```

Даже если `history_trades` успел записаться, при ошибке на шаге statistics **position_info не возвращается** в notify — пользователь видит нули.

### 4.4 Почему не подставились данные из цикла PnL

В `TradeState` к моменту закрытия были актуальные `entry_price`, `current_price`, `pnl_usdt` (лог `📊`), но **уведомление их не использует** — только `closed_info` с биржи/Mongo.

---

## 5. Feed за несколько дней (T11)

- WS держался с 21.05 11:13 до 22.05 22:30 (~**35 ч** активной сессии).
- Много `ping/pong timed out` + failover **primary ↔ backup** — сервис не падал.
- **22:30:54** — штатное `Stopped WS streams for idle symbol BTCUSDT` после release обеих сессий.
- **23.05 18:09** — ручная остановка процесса feed.

---

## 6. Celery heartbeat (T14)

Много `missed heartbeat from engine0/engine1` — Mac sleep / долгие задачи `engine_execute_trade`. На закрытие **22:30** не повлияло; уведомления ушли.

---

## 7. Итоговая оценка прогона

| Аспект | Результат |
|--------|-----------|
| Multi-day удержание позиции | OK (~35 ч до выхода по алгоритму) |
| Два независимых аккаунта | OK |
| Выход по +3% / trailing | OK (логи SL + TS) |
| Отмена limit-ордеров | OK (3 шт. на аккаунт) |
| Feed lifecycle (ensure → release → idle) | OK |
| Личные TG на закрытие | OK (доставка) |
| **Текст PnL / цены в TG** | **FAIL (0/0/0)** |
| **Mongo statistics** | **FAIL (string в sum_positive_trades)** |
| **history_trades + stats атомарность** | **FAIL (ошибка stats отменяет return для notify)** |

**Реальный результат сделки (по engine-логам):** шорт BTCUSDT закрыт в плюсе ~**+28 USDT** (100 USDT профиль) и ~**+44 USDT** (150 USDT профиль) при ~**+3%** движения.

---

## 8. Рекомендуемые исправления (кратко)

См. также раздел «Варианты решения» в чате / задачи на код:

1. **Mongo:** привести `statistics.sum_positive_trades`, `sum_negative_trades`, `total_pnl` к **number** (migration / ручной fix).
2. **Код:** в `_persist_closed_trade` — statistics в отдельном try; при ошибке stats всё равно **return position_info** для notify.
3. **Fallback notify:** если `closed_info` пуст — брать `s.entry_price`, `s.current_price`, `s.pnl_usdt` из `TradeState`.
4. **Порядок:** вызывать `get_result_position_info` **до** `stop_trading` или с небольшой задержкой после закрытия TS (Bybit closed PnL API).
5. **Разделить** insert history и update statistics — не откатывать notify из-за `$inc`.

---

## 9. Источники

| Терминал | Фрагмент |
|----------|----------|
| T11 | Failover, idle stop WS 22:30:54 |
| T12 | engine 0: trailing, stop_trading, Mongo WriteError |
| T13 | engine 1: зеркало закрытия |
| T14 | `send_notification_to_user` оба tg_id |

Связанные файлы: `short_bu_ts_limit_engine.py` (`_persist_closed_trade`, `_check_position_once`), `history_trades_repository.py` (`apply_user_statistics_delta`).
