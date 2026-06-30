"""
Общий изменяемый стейт, используемый из разных модулей хендлеров:
- dp: единый Dispatcher, на который регистрируются все роутеры/хендлеры;
- g_provider: "глобальный" провайдер медиа, нужен для скачивания музыки
  отдельно от основного потока скачивания видео/фото.
"""
from typing import Optional

from aiogram import Dispatcher

from providers import BaseProvider

dp = Dispatcher()

# глобальный provider (нужно для музыки после фото)
g_provider: Optional[BaseProvider] = None


def set_global_provider(provider: BaseProvider) -> None:
    global g_provider
    g_provider = provider
