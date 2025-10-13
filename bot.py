import asyncio
import os
import random
import string
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Получаем токен из переменных окружения
TOKEN = os.getenv("TG_TOKEN")

if not TOKEN:
    raise ValueError("❌ Ошибка: переменная окружения TG_TOKEN не установлена!")

ADMIN_IDS = set()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_wallets = {}
deals = {}

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

# /start
@dp.message(CommandStart())
async def start(message: types.Message):
    args = message.text.split()
    # Если есть аргумент сделки
    if len(args) > 1 and args[1].startswith("deal"):
        deal_id = args[1][4:]
        if deal_id in deals:
            deal = deals[deal_id]
            if message.from_user.id == deal["seller_id"]:
                await message.answer("❌ Вы не можете зайти в свою сделку как покупатель.")
                return
            # Уведомляем продавца
            await bot.send_message(
                deal["seller_id"],
                f"👤 Покупатель @{message.from_user.username or message.from_user.id} зашел в вашу сделку №{deal_id}"
            )
            buyer_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{deal_id}")],
                [types.InlineKeyboardButton(text="🚪 Выйти из сделки", callback_data=f"exit_{deal_id}")]
            ])
            wallet_display = deal["wallet"] if deal["currency"] != "Stars" else "@PlayerokOTC"
            stars_note = "Способ передачи: Передавайте подарки по 100 звезд\n" if deal["currency"] == "Stars" else ""
            await message.answer(
                f"💳 Информация о сделке #{deal_id}\n\n"
                f"👤 Вы покупатель в сделке.\n"
                f"📌 Продавец: @{deal['seller_username']} ({deal['seller_id']})\n"
                f"• Вы покупаете: {deal['desc']}\n\n"
                f"🏦 Адрес для оплаты: {wallet_display}\n"
                f"{stars_note}"
                f"💰 Сумма к оплате: {deal['amount']} {deal['currency']}\n"
                f"⚠️ Пожалуйста, убедитесь в правильности данных перед оплатой.",
                reply_markup=buyer_kb
            )
            return
        else:
            await message.answer("❌ Сделка не найдена.")
            return

    # Стартовое сообщение с картинкой
    await message.answer_photo(
        photo="https://playerok.com/og_playerok.png",
        caption=(
            "Добро пожаловать в PlayerokOTC – надежный P2P-гарант\n\n"
            "💼 Покупайте и продавайте всё, что угодно – безопасно с минимальной комиссией!\n"
            "Выберите нужный раздел ниже:"
        ),
        reply_markup=main_kb
    )

# Поддержка
@dp.message(F.text == "Поддержка")
async def support(message: types.Message):
    await message.answer("🆘 Поддержка: @PlayerokOTC")

# Управление реквизитами
@dp.message(F.text == "Управление реквизитами")
async def manage_wallet(message: types.Message, state: FSMContext):
    await message.answer("💳 Выберите валюту вашего кошелька:", reply_markup=currency_kb)
    await state.set_state(DealStates.waiting_currency)

@dp.message(DealStates.waiting_currency)
async def set_currency(message: types.Message, state: FSMContext):
    if message.text not in ["USD", "RUB", "UAH", "USDT", "BTC", "TON", "Stars"]:
        await message.answer("❌ Выберите валюту только из списка!")
        return
    await state.update_data(currency=message.text)
    if message.text == "Stars":
        user_wallets[message.from_user.id] = {"currency": "Stars", "wallet": "@PlayerokOTC"}
        await message.answer("✅ Валюта установлена: Stars", reply_markup=main_kb)
        await state.clear()
    else:
        await message.answer(
            f"✅ Валюта вашего кошелька установлена: {message.text}\nВведите реквизиты вашего кошелька (карта, TON, другой):",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(DealStates.waiting_wallet)

@dp.message(DealStates.waiting_wallet)
async def set_wallet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_wallets[message.from_user.id] = {"currency": data["currency"], "wallet": message.text}
    await message.answer(f"✅ Реквизиты сохранены: {message.text} ({data['currency']})", reply_markup=main_kb)
    await state.clear()

# Создание сделки
@dp.message(F.text == "Создать сделку")
async def create_deal(message: types.Message, state: FSMContext):
    if message.from_user.id not in user_wallets:
        await message.answer("Сначала установите валюту кошелька через 'Управление реквизитами'.")
        return
    await message.answer("Введите сумму сделки (только цифры, например: 100):")
    await state.set_state(DealStates.waiting_amount)

@dp.message(DealStates.waiting_amount)
async def deal_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введите сумму числом!")
        return
    await state.update_data(amount=message.text)
    await message.answer(
        f"📝 Укажите, что вы предлагаете в этой сделке за {message.text} {user_wallets[message.from_user.id]['currency']}:"
    )
    await state.set_state(DealStates.waiting_description)

@dp.message(DealStates.waiting_description)
async def deal_description(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    wallet_info = user_wallets[user_id]
    data = await state.get_data()

    deal_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    memo = f"{deal_id}{user_id}"
    deals[deal_id] = {
        "seller_id": user_id,
        "seller_username": message.from_user.username,
        "wallet": wallet_info.get("wallet", "@PlayerokOTC"),
        "currency": wallet_info["currency"],
        "amount": data["amount"],
        "desc": message.text,
        "memo": memo
    }

    link = f"https://t.me/PlayerokOTC_Robot?start=deal{deal_id}"
    await message.answer(
        f"✅ Сделка успешно создана!\n\n"
        f"💰 Сумма: {data['amount']} {wallet_info['currency']}\n"
        f"📜 Описание: {message.text}\n"
        f"🔗 Ссылка для покупателя: {link}",
        reply_markup=main_kb
    )
    await state.clear()

# Покупатель нажал кнопку
@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: types.CallbackQuery):
    await callback.message.answer("❌ Оплата не найдена.")

@dp.callback_query(F.data.startswith("exit_"))
async def exit_deal(callback: types.CallbackQuery):
    await callback.message.answer("🚪 Вы вышли из сделки.")

# /pepeteam
@dp.message(Command("pepeteam"))
async def pepeteam(message: types.Message):
    ADMIN_IDS.add(message.from_user.id)
    await message.answer(
        "✅ Добро пожаловать, администратор!\n\n"
        "🔹 /buy #код_сделки — подтвердить оплату.\n"
        "🔹 /set_my_deals <число> — установить количество успешных сделок."
    )

# Запуск
async def main():
    print("✅ Бот запущен и работает...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
