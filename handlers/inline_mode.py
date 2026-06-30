"""
Inline-режим: пользователь пишет в любом чате "@tiksavesbot ссылка_на_tiktok"
и получает карточку для отправки видео/фото без захода в сам бот.

Видео/фото отправляются как ссылки на прямые CDN-файлы TikTok — Telegram
скачивает их сам на своей стороне, поэтому наш сервер не тратит трафик
на inline-скачивания (в отличие от обычного режима через ЛС).

Чтобы это заработало, нужно один раз включить Inline Mode у @BotFather:
/setinline -> выбрать бота -> placeholder текст (например: "Вставь ссылку на TikTok").
"""
import time
import hashlib

from aiogram.types import (
    InlineQuery,
    InlineQueryResultVideo,
    InlineQueryResultPhoto,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from globals_state import dp
import globals_state
from config import CAPTION_VIDEO, CAPTION_PHOTO
from helpers import extract_tiktok_url, normalize_tiktok_url
from storage import store
from logging_channel import log_event, format_user_for_log

# Простой кеш на TTL, чтобы одна и та же ссылка не дёргала API повторно
# при подряд идущих keystroke-запросах inline (Telegram шлёт их часто).
_inline_cache: dict = {}
_INLINE_CACHE_TTL = 60.0


def _cache_get(url: str):
    item = _inline_cache.get(url)
    if not item:
        return None
    media, ts = item
    if time.time() - ts > _INLINE_CACHE_TTL:
        _inline_cache.pop(url, None)
        return None
    return media


def _cache_set(url: str, media) -> None:
    _inline_cache[url] = (media, time.time())
    if len(_inline_cache) > 200:
        oldest = sorted(_inline_cache.items(), key=lambda kv: kv[1][1])[:50]
        for k, _ in oldest:
            _inline_cache.pop(k, None)


@dp.inline_query()
async def inline_query_handler(query: InlineQuery):
    uid = query.from_user.id
    raw = (query.query or "").strip()

    if not raw:
        await query.answer(
            results=[],
            cache_time=1,
            is_personal=True,
            switch_pm_text="Вставь ссылку на TikTok 👆",
            switch_pm_parameter="inline_help",
        )
        return

    url = extract_tiktok_url(raw)
    if not url:
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    id="no_url",
                    title="❌ Это не похоже на ссылку TikTok",
                    description="Вставь корректную ссылку, например https://vt.tiktok.com/...",
                    input_message_content=InputTextMessageContent(
                        message_text="📎 Пришли ссылку на TikTok в чат с ботом, чтобы скачать."
                    ),
                )
            ],
            cache_time=1,
            is_personal=True,
        )
        return

    url = normalize_tiktok_url(url)
    provider = globals_state.g_provider
    if not provider:
        await query.answer(results=[], cache_time=1, is_personal=True)
        return

    is_first_fetch = url not in _inline_cache or _cache_get(url) is None
    media = _cache_get(url)
    if media is None:
        try:
            media = await provider.get_media(url)
            _cache_set(url, media)
        except Exception:
            await query.answer(
                results=[
                    InlineQueryResultArticle(
                        id="err",
                        title="❌ Не удалось обработать ссылку",
                        description="Попробуй ещё раз или открой бота напрямую",
                        input_message_content=InputTextMessageContent(
                            message_text="❌ Не удалось скачать. Попробуй ещё раз чуть позже."
                        ),
                    )
                ],
                cache_time=1,
                is_personal=True,
            )
            return

    results = []
    result_id = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]

    if media.video:
        results.append(
            InlineQueryResultVideo(
                id=f"v_{result_id}",
                video_url=media.video,
                mime_type="video/mp4",
                thumbnail_url=media.photos[0] if media.photos else "https://www.tiktok.com/favicon.ico",
                title="🎬 Отправить видео",
                description="Видео без водяного знака",
                caption=CAPTION_VIDEO,
                parse_mode="HTML",
            )
        )

    if media.photos:
        for i, photo_url in enumerate(media.photos[:5]):
            results.append(
                InlineQueryResultPhoto(
                    id=f"p_{result_id}_{i}",
                    photo_url=photo_url,
                    thumbnail_url=photo_url,
                    title=f"🖼 Фото {i + 1}",
                    caption=CAPTION_PHOTO if i == 0 else None,
                    parse_mode="HTML" if i == 0 else None,
                )
            )

    if not results:
        results.append(
            InlineQueryResultArticle(
                id="empty",
                title="❌ Не нашёл видео/фото по ссылке",
                description="Публикация может быть приватной или удалена",
                input_message_content=InputTextMessageContent(
                    message_text="❌ Не удалось найти медиа по этой ссылке."
                ),
            )
        )

    await query.answer(results=results, cache_time=30, is_personal=True)

    if is_first_fetch and results:
        store.register(uid)
        label = store.get_user_label(uid)  # из кеша, без живого API-запроса
        await log_event(
            query.bot,
            "inline",
            [
                "🔎 Категория: <b>Inline-запрос</b>",
                f"👤 User/id: <b>{format_user_for_log(label, uid)}</b>",
                f"🔗 Ссылка: {url}",
            ],
        )
