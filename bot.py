"""
Точка входа: поднимает aiohttp-сессию, провайдеров, фоновые задачи
(автосейв, лог-воркер, рассылки, ежемесячный отчёт) и запускает polling.
"""
import asyncio
import contextlib
from typing import Optional

import aiohttp
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ALT_PROVIDER, log
from helpers import now_msk_str
from storage import store, init_db, close_db
import globals_state
from globals_state import dp
from providers import TikWMClient, ApifyProvider, BaseProvider, ProviderSwitcher
from logging_channel import autosave_loop, start_log_worker, stop_log_worker, send_channel_log
from broadcast import broadcast_schedule_loop
from db_report import start_monthly_report, stop_monthly_report

# Импорт регистрирует все хендлеры (@dp.message/@dp.callback_query) на dp.
import handlers  # noqa: F401

_autosave_task: Optional[asyncio.Task] = None
_broadcast_task: Optional[asyncio.Task] = None
_monthly_task: Optional[asyncio.Task] = None


async def main():
    global _autosave_task, _broadcast_task, _monthly_task

    # 1) Инициализируем БД (создаём таблицы, мигрируем из JSON если нужно)
    await init_db()

    # 2) Загружаем данные в память
    await store.load_from_db()

    timeout = aiohttp.ClientTimeout(total=90, sock_connect=20, sock_read=45)
    connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

        primary = TikWMClient(session, bot=bot)
        secondary: Optional[BaseProvider] = None
        if ALT_PROVIDER == "apify":
            secondary = ApifyProvider(session, bot)

        switcher = ProviderSwitcher(primary, secondary, bot)
        globals_state.set_global_provider(primary)

        await start_log_worker(bot)

        _autosave_task = asyncio.create_task(autosave_loop())
        _broadcast_task = asyncio.create_task(broadcast_schedule_loop(bot))
        _monthly_task = start_monthly_report(bot)

        try:
            me = await bot.get_me()
            await send_channel_log(
                bot,
                "🚀 Бот запущен\n"
                f"🤖 @{me.username} ({me.id})\n"
                f"👥 Пользователей: {len(store.data.get('users', []))}\n"
                f"🕒 {now_msk_str()}",
            )
            await dp.start_polling(bot, client=primary, switcher=switcher)
        finally:
            for task in (_autosave_task, _broadcast_task, _monthly_task):
                if task and not task.done():
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await task

            await store.save_unthrottled()
            await stop_log_worker()
            await close_db()


if __name__ == "__main__":
    asyncio.run(main())
