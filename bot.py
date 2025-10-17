import asyncio
import random
import string
import os
from typing import Dict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = os.getenv("BOT_TOKEN")  # Fly.io environment variable
ADMIN_IDS = set()

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

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Добро пожаловать в PlayerokOTC!\nВыберите нужный раздел ниже:",
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
    await message.answer(f"Введите реквизиты вашего кошелька для {chosen}:", reply_markup=types.ReplyKeyboardRemove())
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
    if not message.text.isdigit():
        await message.answer("❌ Введите сумму только цифрами.")
        return
    await state.update_data(amount=message.text.strip())
    currency = user_wallets[message.from_user.id]["currency"]
    await message.answer(f"📝 Укажите, что вы предлагаете в этой сделке за {message.text.strip()} {currency}:")
    await state.set_state(DealStates.waiting_description)

@dp.message(DealStates.waiting_description)
async def deal_description(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    amount = data.get("amount")
    desc = message.text.strip()
    wallet_info = user_wallets.get(user_id, {"currency": "USD", "wallet": "None"})
    deal_id = gen_deal_id()
    deals[deal_id] = {
        "seller_id": user_id,
        "seller_username": message.from_user.username or str(user_id),
        "wallet": wallet_info["wallet"],
        "currency": wallet_info["currency"],
        "amount": amount,
        "desc": desc,
        "buyer_id": None
    }
    link = f"https://t.me/PlayerokOTC_Robot?start=deal{deal_id}"
    await message.answer(f"✅ Сделка создана!\n💰 Сумма: {amount} {wallet_info['currency']}\n📜 Описание: {desc}\n🔗 Ссылка для покупателя: {link}", reply_markup=main_kb)
    await state.clear()

async def main():
    print("✅ Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
