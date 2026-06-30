# TikSaves Bot

Telegram-бот для скачивания видео/фото/музыки из TikTok (aiogram 3.29+).

## Запуск

```bash
pip install -r requirements.txt
cp .env.example .env   # заполни BOT_TOKEN
python bot.py
```

## Структура

```
tiksaves_bot/
├── bot.py                 # точка входа (main, polling)
├── config.py               # переменные окружения, константы
├── helpers.py                # HTML/даты/URL утилиты, парсинг длительности бана
├── storage.py                  # класс Storage (data.json) — пользователи, баны, страйки, статистика
├── admin_log_file.py             # текстовый лог-файл (admin.log)
├── logging_channel.py              # буферизованные логи в Telegram-канал + автосейв
├── user_label.py                     # resolve_user_label (имя/юзернейм для логов)
├── limiters.py                         # анти-флуд, лимит скачиваний/фото
├── strikes.py                            # страйки и авто-баны
├── gates.py                                # проверка бана + анти-флуд перед хендлерами
├── providers.py                              # TikWMClient / ApifyProvider / ProviderSwitcher
├── globals_state.py                            # общий Dispatcher (dp) и текущий provider
├── send_helpers.py                               # отправка фото-альбомов/видео/музыки
├── picker_state.py                                 # состояние фото-пикера
├── keyboards.py                                      # инлайн-клавиатуры и тексты UI
├── donate.py                                           # логика донатов / Stars-инвойсов
├── broadcast.py                                          # ручная и плановая рассылка
├── stats.py                                                # тексты статистики/топов
└── handlers/
    ├── __init__.py            # регистрирует все хендлеры на dp
    ├── commands.py              # /start /help /support /donate /admin /stats /top
    ├── admin_commands.py          # /ban /unban /banlist /baninfo /info /broadcast ...
    ├── strikes_commands.py          # /strikes /strikeadd /strikedel
    ├── admin_callbacks.py             # кнопки админ-панели (ad:*)
    ├── donate_callbacks.py              # кнопки донатов/Stars (dl:*, donate:*, stars:*)
    ├── help_callbacks.py                  # кнопки раздела помощи (help:*)
    ├── picker_callbacks.py                  # кнопки фото-пикера (pk:*)
    ├── video_choice_callbacks.py               # задел на выбор перед видео (vd:*, сейчас не используется)
    └── main_handler.py                           # основной catch-all обработчик ссылок
```

## Заметки

- `video_choice_callbacks.py` / `picker_state.pending_video` сохранены как есть из
  оригинала, но сейчас не используются: `main_handler` отправляет видео сразу,
  без промежуточного экрана выбора. Это не баг, просто незавершённая ветка функционала.
- Данные хранятся в `data.json` рядом с `bot.py` (создаётся автоматически).
- Для резервного провайдера скачивания установи `ALT_PROVIDER=apify` и `APIFY_TOKEN`
  в `.env` — но `ApifyProvider.get_media` потребует доработки (маппинг полей актора).
