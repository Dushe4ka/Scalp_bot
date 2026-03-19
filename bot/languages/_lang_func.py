from bot.languages.ru import RU_CONFIGURATION
from bot.languages.en import EN_CONFIGURATION

async def get_config_lang(language: str) -> dict:
    """Получение конфигурации языка"""
    if language == "ru":
        return RU_CONFIGURATION
    elif language == "en":
        return EN_CONFIGURATION
    else:
        return RU_CONFIGURATION