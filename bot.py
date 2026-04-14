#!/usr/bin/env python3
"""
AI News Bot — Subscription Bot

Lets Telegram users choose which news channels they want to receive
via an interactive inline keyboard menu.

Usage:
  python bot.py

Commands (in Telegram):
  /start      — Welcome message + quick intro
  /subscribe  — Open channel selection menu
  /mystatus   — Show current subscriptions
  /unsubscribe — Remove all subscriptions
"""
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

from src.db import Database

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_AI_BOT_TOKEN", "")

# ── Channel definitions (order controls display) ───────────────────────────────
CHANNELS = [
    {"key": "ai",         "title": "🤖 AI News"},
    {"key": "medical",    "title": "🏥 Medical News"},
    {"key": "pharma",     "title": "💊 Pharma News"},
    {"key": "genome",     "title": "🧬 Genome Research"},
    {"key": "genetics",   "title": "🔬 Genetics Research"},
    {"key": "energy",     "title": "⚡ Energy News"},
    {"key": "rare_earth", "title": "⛏️ Rare Earth News"},
    {"key": "psychology", "title": "🧠 Psychology News"},
    {"key": "sports",         "title": "🏆 Sports News"},
    {"key": "finance",        "title": "💰 Finance News"},
    {"key": "entertainment",  "title": "🎬 Entertainment News"},
    {"key": "music",          "title": "🎵 Music News"},
]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_keyboard(subscribed: set) -> InlineKeyboardMarkup:
    """Build the channel toggle keyboard, reflecting current subscriptions."""
    rows = []
    row = []
    for ch in CHANNELS:
        icon = "✅" if ch["key"] in subscribed else "☑️"
        row.append(InlineKeyboardButton(
            text=f"{icon} {ch['title']}",
            callback_data=f"toggle:{ch['key']}",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="💾 Save preferences", callback_data="save")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Command handlers ───────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "<b>👋 Welcome to AI News Bot!</b>\n\n"
        "I send daily digests across 12 news channels:\n\n"
        "🤖 AI News  •  🏥 Medical  •  💊 Pharma\n"
        "🧬 Genome  •  🔬 Genetics  •  ⚡ Energy\n"
        "⛏️ Rare Earth  •  🧠 Psychology  •  🏆 Sports\n"
        "💰 Finance  •  🎬 Entertainment  •  🎵 Music\n\n"
        "Use /subscribe to pick which channels you want.\n"
        "Use /mystatus to see your active subscriptions.",
        parse_mode="HTML",
    )


@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    chat_id = str(message.chat.id)
    subscribed = db.get_user_channels(chat_id)
    await message.answer(
        "<b>Select your news channels:</b>\n"
        "Tap to toggle ✅ / ☑️, then tap <b>💾 Save preferences</b>.",
        reply_markup=_build_keyboard(subscribed),
        parse_mode="HTML",
    )


@dp.message(Command("mystatus"))
async def cmd_mystatus(message: Message) -> None:
    chat_id = str(message.chat.id)
    subscribed = db.get_user_channels(chat_id)
    if not subscribed:
        await message.answer(
            "You have no active subscriptions.\nUse /subscribe to set them up."
        )
        return
    names = [ch["title"] for ch in CHANNELS if ch["key"] in subscribed]
    await message.answer(
        "<b>Your active subscriptions:</b>\n" + "\n".join(f"• {n}" for n in names),
        parse_mode="HTML",
    )


@dp.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message) -> None:
    chat_id = str(message.chat.id)
    db.clear_user(chat_id)
    await message.answer("✅ All subscriptions removed. Use /subscribe to start again.")


# ── Callback handlers ──────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("toggle:"))
async def cb_toggle(callback: CallbackQuery) -> None:
    chat_id = str(callback.message.chat.id)
    key = callback.data.split(":", 1)[1]
    subscribed = db.get_user_channels(chat_id)
    if key in subscribed:
        db.remove_channel(chat_id, key)
        subscribed.discard(key)
    else:
        db.add_channel(chat_id, key)
        subscribed.add(key)
    await callback.message.edit_reply_markup(reply_markup=_build_keyboard(subscribed))
    await callback.answer()


@dp.callback_query(F.data == "save")
async def cb_save(callback: CallbackQuery) -> None:
    chat_id = str(callback.message.chat.id)
    subscribed = db.get_user_channels(chat_id)
    if subscribed:
        names = [ch["title"] for ch in CHANNELS if ch["key"] in subscribed]
        text = (
            "<b>✅ Preferences saved!</b>\n\n"
            "<b>You'll receive daily digests for:</b>\n"
            + "\n".join(f"• {n}" for n in names)
        )
    else:
        text = "⚠️ No channels selected. Use /subscribe to choose channels."
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer("Preferences saved!")


# ── Entry point ────────────────────────────────────────────────────────────────

async def _main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_AI_BOT_TOKEN is not set in .env")
    print("Subscription bot is running. Press Ctrl+C to stop.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(_main())
