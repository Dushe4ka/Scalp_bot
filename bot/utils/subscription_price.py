"""Динамическая цена подписки: парсинг админского ввода и форматирование текста."""
from __future__ import annotations


def format_price(value: float) -> str:
    """59.0 -> '59', 59.5 -> '59.5' — без лишних нулей после запятой."""
    text = f"{float(value):g}"
    return text


def parse_admin_price_input(text: str) -> tuple[float, float | None]:
    """
    Разбирает ввод админа при смене цены подписки.

    Форматы:
    - "59"      -> (59.0, None)       — меняется только текущая цена
    - "59/79"   -> (59.0, 79.0)       — меняются текущая и старая (зачёркиваемая) цена

    Raises:
        ValueError: пустой/нечисловой ввод, неположительная цена,
            старая цена не больше новой, или больше двух значений.
    """
    parts = [p.strip() for p in (text or "").split("/")]
    if len(parts) not in (1, 2):
        raise ValueError(f"Ожидается 1 или 2 значения через '/', получено: {text!r}")

    try:
        price = float(parts[0])
    except ValueError as e:
        raise ValueError(f"Некорректная цена: {parts[0]!r}") from e
    if price <= 0:
        raise ValueError(f"Цена должна быть положительной: {price}")

    old_price: float | None = None
    if len(parts) == 2:
        try:
            old_price = float(parts[1])
        except ValueError as e:
            raise ValueError(f"Некорректная старая цена: {parts[1]!r}") from e
        if old_price <= price:
            raise ValueError(
                f"Старая цена ({old_price}) должна быть больше новой ({price})"
            )

    return price, old_price
