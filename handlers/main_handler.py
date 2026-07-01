"""
Основной обработчик текстовых сообщений: распознаёт TikTok-ссылку,
скачивает медиа и отправляет видео/фото-пикер/музыку. Также обрабатывает
ввод кастомной суммы донат-Stars, если пользователь её ожидает.

client и switcher приходят через aiogram workflow_data (см. dp.start_polling
в bot.py: client=primary, switcher=switcher) — aiogram сам инжектирует их
в хендлер по совпадению имени параметра.
"""
import time
import contextlib

import aiohttp
from aiogram import F
from aiogram.types import Message, LinkPreviewOptions

from globals_state import dp
from config import (
    STARS_MIN,
    STARS_MAX,
    WAITING_STARS_TTL_SEC,
    MSG_DL,
    CAPTION_VIDEO,
)
from helpers import (
    clamp_reason,
    extract_tiktok_url,
    normalize_tiktok_url,
    resolve_tiktok_redirect,
    is_admin,
    pe,
)
from storage import store
from user_label import resolve_user_label
from gates import gate_message
from limiters import lim, download_sem
from strikes import add_download_strike
from providers import TikWMClient, ProviderSwitcher
from send_helpers import send_video_smart
from picker_state import pending, cleanup_pending, last_audio_url, last_video_src, last_video_desc, picker_kb
from keyboards import under_video_kb
from donate import waiting_stars_amount, send_stars_invoice
from logger import logger, Event, Stopwatch


@dp.message(F.text)
async def main_handler(message: Message, client: TikWMClient, switcher: ProviderSwitcher):
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text:
        return

    label = await resolve_user_label(message.bot, uid)
    store.set_user_label(uid, label)

    if not await gate_message(message, label):
        return

    # custom stars amount
    ts_wait = waiting_stars_amount.get(uid)
    if ts_wait:
        if time.time() - ts_wait > WAITING_STARS_TTL_SEC:
            waiting_stars_amount.pop(uid, None)
        else:
            if text.isdigit():
                stars = int(text)
                if not (STARS_MIN <= stars <= STARS_MAX):
                    await message.answer(pe(f"❌ Сумма должна быть {STARS_MIN}–{STARS_MAX} ⭐"), parse_mode="HTML")
                    return
                waiting_stars_amount.pop(uid, None)
                await send_stars_invoice(message.bot, uid, stars)
                return

    store.register(uid)

    url = extract_tiktok_url(text)
    if url:
        url = normalize_tiktok_url(url)
        last_video_src[uid] = url
    if not url and not text.startswith("/"):
        await message.answer(pe("📎 Пришли ссылку на TikTok."), parse_mode="HTML")
        return

    if text.startswith("/"):
        return

    if not is_admin(uid):
        ok_dl, wait_dl = lim.dl_hit(uid)
        if not ok_dl:
            await message.answer(MSG_DL.format(n=wait_dl))
            await add_download_strike(
                message.bot,
                uid,
                label,
                "Лимит скачиваний",
                src=url or text,
            )
            return

    status = await message.answer(pe("⏳ Скачиваю…"), parse_mode="HTML")
    sw = Stopwatch()
    provider_name = ""

    try:
        async with download_sem:
            with contextlib.suppress(Exception):
                await status.edit_text(pe("⏳ Скачиваю…"), parse_mode="HTML")
            provider = switcher.choose()
            provider_name = type(provider).__name__
            try:
                media = await provider.get_media(url or text)
            except Exception:
                # retry with resolved redirect for short links
                sess = getattr(provider, "session", None)
                if sess and url:
                    resolved = await resolve_tiktok_redirect(sess, url)
                    resolved = normalize_tiktok_url(resolved)
                    if resolved and resolved != url:
                        media = await provider.get_media(resolved)
                    else:
                        raise
                else:
                    raise
            sw.lap("get_info")

            video, photos, music = media.video, media.photos, media.music
            description = media.description
            if music:
                last_audio_url[uid] = music

            if photos:
                cleanup_pending()
                pending[uid] = {
                    "photos": photos,
                    "music": music,
                    "description": description,
                    "desc_selected": False,
                    "video_slideshow": video,
                    "selected": set(),
                    "page": 0,
                    "ts": time.time(),
                    "src": url or text,
                }
                with contextlib.suppress(Exception):
                    await status.edit_text(pe("🖼️ Выбери фото по номерам или выдели страницу 👇"), parse_mode="HTML", reply_markup=picker_kb(uid))
                logger.log(
                    Event.DOWNLOAD,
                    "Фото-альбом найден",
                    status="SUCCESS",
                    user={"id": uid, "username": label if label.startswith("@") else None},
                    content={"type": "photo_album", "provider": provider_name, "source": url or text},
                    performance=sw.as_dict(),
                )
                return

            if not video:
                raise RuntimeError("No media links (video/photo missing)")

            if description:
                last_video_desc[uid] = description
            else:
                last_video_desc.pop(uid, None)

            # Сразу отправляем видео; кнопки «Описание»/«Музыка» — под видео
            await send_video_smart(
                message,
                provider,
                video,
                CAPTION_VIDEO,
                status_msg=status,
                reply_markup=under_video_kb(has_music=bool(music), has_desc=bool(description)),
            )
            sw.lap("download_and_send")
            store.inc_download(uid, "video", items=1)
            with contextlib.suppress(Exception):
                await status.delete()

            logger.log(
                Event.DOWNLOAD,
                "Видео скачано",
                status="SUCCESS",
                user={"id": uid, "username": label if label.startswith("@") else None},
                content={"type": "video", "provider": provider_name, "source": url or text},
                performance=sw.as_dict(),
            )

    except aiohttp.ClientError as e:
        store.inc_error("handler", e)
        with contextlib.suppress(Exception):
            await status.edit_text(pe("❌ Проблема с сетью/сервисом. Попробуй позже."), parse_mode="HTML")

        logger.log_exception(
            e,
            module="handlers.main_handler",
            user={"id": uid, "username": label if label.startswith("@") else None},
            provider=provider_name,
            url=url or text,
            duration_ms=sw.total_ms(),
            title="Сетевая ошибка при скачивании",
        )

    except Exception as e:
        reason = clamp_reason(e)
        low = reason.lower()

        # Видео слишком большое — тихая ошибка, не логируем в канал
        if "file too large" in low:
            with contextlib.suppress(Exception):
                await status.edit_text(pe("❌ Видео слишком большое для отправки через Telegram (лимит 60 МБ)."), parse_mode="HTML")
            return

        store.inc_error("handler", e)
        msg = "❌ Не удалось скачать. Попробуй позже."
        if any(x in low for x in ["private", "приват", "недоступ", "unavailable"]):
            msg = "❌ Видео приватное или недоступно."
        elif any(x in low for x in ["deleted", "удален", "removed", "not found"]):
            msg = "❌ Видео удалено или не найдено."
        elif "url parsing" in low:
            msg = "❌ Не удалось разобрать ссылку. Проверь ссылку и попробуй ещё раз."
        elif "timeout" in low or "timed out" in low:
            msg = "❌ Сервер TikTok долго отвечает. Попробуй ещё раз через минуту."
        with contextlib.suppress(Exception):
            await status.edit_text(pe(msg), parse_mode="HTML")

        logger.log_exception(
            e,
            module="handlers.main_handler",
            user={"id": uid, "username": label if label.startswith("@") else None},
            provider=provider_name,
            url=url or text,
            duration_ms=sw.total_ms(),
            title="Ошибка при скачивании",
        )
