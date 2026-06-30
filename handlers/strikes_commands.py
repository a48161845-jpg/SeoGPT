"""
Команды управления страйками — оставлены для совместимости,
но страйки удалены из системы. Команды выводят соответствующее сообщение.
"""
from aiogram.filters import Command
from aiogram.types import Message

from globals_state import dp
from helpers import is_admin, code
from gates import gate_message
from user_label import resolve_user_label
from storage import store


@dp.message(Command("strikes", "strike"))
async def strikes_cmd(message: Message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        return
    await message.answer(
        "ℹ️ Система страйков отключена.\n"
        "Используется тихий анти-спам лимит без накопления страйков.\n\n"
        "Для управления банами используй /ban и /unban.",
        parse_mode="HTML",
    )


@dp.message(Command("strikeadd"))
async def strikeadd_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("ℹ️ Страйки отключены. Используй /ban для ручного бана.", parse_mode="HTML")


@dp.message(Command("strikedel"))
async def strikedel_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("ℹ️ Страйки отключены.", parse_mode="HTML")


@dp.message(Command("strikeclear"))
async def strikeclear_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("ℹ️ Страйки отключены.", parse_mode="HTML")
