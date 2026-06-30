"""
Пошаговый сценарий рассылки: /broadcast запускает wizard, который ловит
следующие сообщения админа (текст, потом фото) и callback-кнопки.

Поток: текст -> фото (или пропустить) -> итог с кнопками:
  📌 (toggle закреп вкл/выкл прямо на итоговом экране) · 🚀 Разослать · ❌ Отменить

ВАЖНО: в aiogram 3.x, если хендлер подошёл по фильтрам, апдейт считается
обработанным и дальше НЕ передаётся. Поэтому здесь используется фильтр-функция
(_wizard_text_active / _wizard_photo_active), которая возвращает False, если
визард не активен для этого uid — тогда aiogram сам идёт к следующему
хендлеру (main_handler), а не наш код внутри функции с "return".

ФОРМАТИРОВАНИЕ: текст рассылки сохраняется с учётом реального форматирования
Telegram (жирный/курсив/подчёркивание и т.д., применённые через нативную
панель форматирования при зажатии текста), а НЕ через markdown-символы
вроде **текст**. Это делается через message.entities + html_decoration.unparse —
тот же механизм, что Telegram использует сам для конвертации форматированного
текста в HTML.
"""
import contextlib

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.text_decorations import html_decoration

from globals_state import dp
from helpers import is_admin, html_escape, pe
from storage import store
from user_label import resolve_user_label
from gates import gate_callback
from admin_log_file import log_admin
from keyboards import bcw_skip_photo_kb, bcw_result_kb
from broadcast import broadcast_wizard, do_broadcast


def _users_count() -> int:
    return len(store.data.get("users", []))


def _wizard_text_active(message: Message) -> bool:
    uid = message.from_user.id if message.from_user else None
    if uid is None or not is_admin(uid):
        return False
    st = broadcast_wizard.get(uid)
    return bool(st and st.get("step") == "text")


def _wizard_photo_active(message: Message) -> bool:
    uid = message.from_user.id if message.from_user else None
    if uid is None or not is_admin(uid):
        return False
    st = broadcast_wizard.get(uid)
    return bool(st and st.get("step") == "photo")


def _message_to_html(message: Message) -> str:
    """
    Конвертирует текст сообщения с учётом реальных Telegram-entities
    (жирный/курсив/подчёркивание/ссылки и т.д., применённые через нативную
    панель форматирования) в HTML. Если entities нет — просто экранированный текст.
    """
    raw = message.text or ""
    entities = message.entities or []
    if not entities:
        return html_escape(raw)
    try:
        return html_decoration.unparse(raw, entities)
    except Exception:
        return html_escape(raw)


@dp.message(F.text, ~F.text.startswith("/"), _wizard_text_active)
async def broadcast_wizard_text(message: Message):
    uid = message.from_user.id

    st = broadcast_wizard[uid]
    raw = (message.text or "").strip()
    if not raw:
        await message.answer(pe("❌ Текст не может быть пустым. Пришлите текст рассылки ещё раз."), parse_mode="HTML")
        return

    st["text"] = _message_to_html(message)
    st["step"] = "photo"

    await message.answer(
        pe("Шаг 2/2: пришлите фото для рассылки.\nЕсли фото не нужно — нажмите «Пропустить»."),
        parse_mode="HTML",
        reply_markup=bcw_skip_photo_kb(),
    )


@dp.message(F.photo, _wizard_photo_active)
async def broadcast_wizard_photo(message: Message):
    uid = message.from_user.id
    st = broadcast_wizard[uid]

    file_id = message.photo[-1].file_id
    st["photo"] = file_id
    st["step"] = "result"

    await _show_result(message, uid)


async def _show_result(message: Message, uid: int) -> None:
    """
    Итоговый экран = ровно то, что увидят получатели (текст + фото, если есть),
    плюс кнопки управления: 📌 закреп (toggle), 🚀 Разослать, ❌ Отменить.
    Без какого-либо служебного текста поверх — только реальный контент рассылки.
    """
    st = broadcast_wizard.get(uid)
    if not st:
        return
    text = st.get("text") or ""  # уже готовый HTML (из message.entities)
    photo = st.get("photo")
    pin = bool(st.get("pin"))

    if photo:
        await message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=bcw_result_kb(pin))
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=bcw_result_kb(pin))


@dp.callback_query(F.data.startswith("bcw:"))
async def broadcast_wizard_cb(call: CallbackQuery):
    uid = call.from_user.id
    label = await resolve_user_label(call.bot, uid)
    store.set_user_label(uid, label)

    if not is_admin(uid):
        await call.answer("Нет доступа.", show_alert=True)
        return
    if not await gate_callback(call, label):
        return
    if not call.message:
        await call.answer()
        return

    st = broadcast_wizard.get(uid)
    action = (call.data or "").split(":", 1)[-1]

    if action == "abort":
        broadcast_wizard.pop(uid, None)
        await call.answer("Рассылка отменена.")
        with contextlib.suppress(Exception):
            await call.message.delete()
        return

    if not st:
        await call.answer("Сценарий рассылки устарел. Запусти /broadcast заново.", show_alert=True)
        return

    if action == "skip_photo":
        if st.get("step") != "photo":
            await call.answer()
            return
        st["photo"] = None
        st["step"] = "result"
        await call.answer()
        with contextlib.suppress(Exception):
            await call.message.delete()
        await _show_result(call.message, uid)
        return

    if action == "toggle_pin":
        if st.get("step") != "result":
            await call.answer()
            return
        st["pin"] = not bool(st.get("pin"))
        await call.answer("📌 Закреп включён" if st["pin"] else "📌 Закреп выключен")
        with contextlib.suppress(Exception):
            await call.message.edit_reply_markup(reply_markup=bcw_result_kb(bool(st["pin"])))
        return

    if action == "send":
        if st.get("step") != "result":
            await call.answer()
            return
        await call.answer("🚀 Запускаю рассылку…")
        text = st.get("text") or ""
        photo = st.get("photo")
        pin = bool(st.get("pin"))
        broadcast_wizard.pop(uid, None)
        with contextlib.suppress(Exception):
            await call.message.delete()
        log_admin(uid, "broadcast_wizard_send", f"photo={bool(photo)} pin={pin}")
        await do_broadcast(call.message, uid, label, text, already_html=True, photo=photo, pin=pin)
        return

    await call.answer()
