import asyncio
import os
import random
import string
from typing import Dict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ====== Настройки ======
TOKEN = os.getenv("BOT_TOKEN")  # Токен из секретов Fly.io
ADMIN_IDS = set()
# =======================

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_wallets: Dict[int, Dict] = {}
deals: Dict[str, Dict] = {}

class DealStates(StatesGroup):
    waiting_currency = State()
    waiting_wallet = State()
    waiting_amount = State()
    waiting_description = State()

# Основные кнопки
main_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="Управление реквизитами"), types.KeyboardButton(text="Создать сделку")],
        [types.KeyboardButton(text="Реферальная ссылка"), types.KeyboardButton(text="Поддержка")]
    ],
    resize_keyboard=True
)

# Клавиатура для выбора валюты
currency_kb = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text=c)] for c in ["USD", "RUB", "UAH", "USDT", "BTC", "TON", "Stars"]],
    resize_keyboard=True
)

def gen_deal_id() -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

# ====== /start ======
@dp.message(CommandStart())
async def start(message: types.Message):
    text = (
        "Добро пожаловать в PlayerokOTC – надежный P2P-гарант\n\n"
        "💼 Покупайте и продавайте безопасно с минимальной комиссией!\n"
        "Выберите нужный раздел ниже:"
    )
    photo_url = "https://playerok.com/og_playerok.png"

    # Если передан deal в ссылке /start dealXXXX
    parts = (message.text or "").split()
    if len(parts) > 1 and parts[1].startswith("deal"):
        deal_id = parts[1][4:]
        if deal_id in deals:
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
                f"📝 Комментарий к платежу (мемо): {deal['memo']}\n\n"
                f"⚠️ Убедитесь в правильности данных перед оплатой.",
                reply_markup=buyer_kb
            )
            return

    # Основной старт с картинкой
    await message.answer_photo(photo=photo_url, caption=text, reply_markup=main_kb)

# ====== Поддержка ======
@dp.message(F.text == "Поддержка")
async def support(message: types.Message):
    await message.answer("🆘 Поддержка: @PlayerokOTC")

# ====== Управление реквизитами ======
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
    await message.answer(f"✅ Валюта установлена: {chosen}\nВведите реквизиты вашего кошелька:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(DealStates.waiting_wallet)

@dp.message(DealStates.waiting_wallet)
async def set_wallet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency")
    user_wallets[message.from_user.id] = {"currency": currency, "wallet": message.text.strip()}
    await message.answer(f"✅ Реквизиты сохранены: {message.text.strip()} ({currency})", reply_markup=main_kb)
    await state.clear()

# ====== Создание сделки ======
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

# ====== Callback для покупателя ======
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

# ====== Админ команды ======
@dp.message(Command(commands=["pepeteam"]))
async def pepeteam(message: types.Message):
    ADMIN_IDS.add(message.from_user.id)
    await message.answer("✅ Вы теперь админ!")

# ====== Запуск ======
async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
