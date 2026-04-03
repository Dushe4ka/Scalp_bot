def frange(start: float, stop: float, step: float) -> list[float]:
    """
    Генерирует список чисел с заданным шагом
    Args:
        start: начальное значение
        stop: конечное значение
        step: шаг
    Returns:
        list[float]: список чисел
    """
    result = []
    i = start
    while (step > 0 and i <= stop) or (step < 0 and i >= stop):
        result.append(i)
        i += step
    return result