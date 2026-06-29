import asyncio
import os
import aiohttp
import numpy as np

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# 📚 БАЗА ЗНАНИЙ (ТВОЯ)
# =========================

BASE_CONTEXT = """
Ты — умный FAQ-ассистент SEO Telegram-бота.

ОТВЕЧАЙ ТОЛЬКО ПО ЭТИМ ДАННЫМ.
НЕ ВЫДУМЫВАЙ.

━━━━━━━━━━━━━━━━━━━━━━
⚠️ ПРАВИЛА
━━━━━━━━━━━━━━━━━━━━━━
• Только кнопки или чат
• Нарушения → бан
• Поддержка: https://t.me/Seo_Sup_Bot

━━━━━━━━━━━━━━━━━━━━━━
📢 РЕСУРСЫ
━━━━━━━━━━━━━━━━━━━━━━
Новости: https://t.me/seonewschannel
Чат: https://t.me/+6CsuSYsqW6VlMTI6
Отзывы: https://t.me/seootzyvs_official
Поддержка: https://t.me/seo_sup_bot
Задания: https://t.me/Seo_Task

━━━━━━━━━━━━━━━━━━━━━━
💰 РЕФЕРАЛКА
━━━━━━━━━━━━━━━━━━━━━━
1 уровень = 20%
2 уровень = 5%

━━━━━━━━━━━━━━━━━━━━━━
💸 ЗАДАНИЯ
━━━━━━━━━━━━━━━━━━━━━━

Яндекс:
- отзыв 120 ₽ + 300 SeoCoin
- оценка 5 ₽ + 20 SeoCoin
- услуги 25 ₽
- сайты 40 ₽

Google:
- отзыв 25 ₽
- оценка 10 ₽

2GIS:
- отзыв 25 ₽

YouTube:
- лайк 2 ₽
- подписка 5 ₽

VK:
- подписка 5 ₽
- комментарий 10 ₽

Instagram:
- лайк 2 ₽
- подписка 5 ₽

Telegram:
- подписка 1 ₽
- комментарий 0.4 ₽

━━━━━━━━━━━━━━━━━━━━━━
📦 ВЫВОД
━━━━━━━━━━━━━━━━━━━━━━
• ЮMoney от 150 ₽
• Карты РФ от 300 ₽
• CryptoBot от 100 ₽
• Телефон от 150 ₽

━━━━━━━━━━━━━━━━━━━━━━
📊 SEO COIN
━━━━━━━━━━━━━━━━━━━━━━
• за задания
• за рефералов
• за активность

━━━━━━━━━━━━━━━━━━━━━━
🚫 ПРАВИЛА
━━━━━━━━━━━━━━━━━━━━━━
• мультиаккаунты запрещены
• дубли заданий запрещены
• бан за нарушения
"""


# =========================
# 🧠 "УМНЫЙ ПОИСК" (очень лёгкий смысловой матч)
# =========================

FAQ_DB = {
    "телеграм": "Telegram: подписка 1₽ + 20 SeoCoin, комментарий 0.4₽ + 20 SeoCoin",
    "реферал": "Рефералы: 1 уровень 20%, 2 уровень 5%",
    "вывод": "Вывод: ЮMoney 150₽+, карты 300₽+, CryptoBot 100₽+",
    "яндекс": "Яндекс задания: отзывы до 120₽ + SeoCoin",
    "youtube": "YouTube: лайк 2₽, подписка 5₽"
}


def simple_semantic_search(text: str):
    text = text.lower()

    best_key = None
    best_score = 0

    for k in FAQ_DB.keys():
        score = sum(1 for word in k.split() if word in text)
        if score > best_score:
            best_score = score
            best_key = k

    return FAQ_DB.get(best_key)


# =========================
# 🤖 OPENROUTER ОТВЕТ
# =========================

async def ask_ai(question: str, context: str):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    BASE_CONTEXT +
                    "\n\nТы должен отвечать ТОЛЬКО по базе. "
                    "Если данных нет — скажи: 'Информация отсутствует в базе FAQ.'"
                )
            },
            {
                "role": "user",
                "content": f"Вопрос: {question}\n\nНайденные данные: {context}"
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as r:
            data = await r.json()
            return data["choices"][0]["message"]["content"]


# =========================
# 🚀 BOT HANDLER
# =========================

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("👋 SEO Bot активен\nЗадай вопрос в чат")


@dp.message()
async def handler(m: Message):
    question = m.text

    # 1. ищем по смыслу
    context = simple_semantic_search(question)

    # 2. если нет — говорим честно
    if not context:
        await m.answer("❗ Информация отсутствует в базе FAQ.")
        return

    # 3. формируем ответ через AI
    answer = await ask_ai(question, context)

    await m.answer(answer)


# =========================
# ▶️ RUN
# =========================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
