import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
import aiohttp
from fpdf import FPDF
import os
from parser import get_usdt_buy_price, get_usdt_sell_price

# Настройки бота
API_TOKEN = '7865935276:AAHnnOtaXCfhAy3FqTgvCaW2p5SxgnVLeQ0'
MANAGER_ID = 1086033998
MANAGER_LINK = 'https://t.me/latnikova_d'
ADMIN_ID = 1086033998

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# Настройка базы данных
conn = sqlite3.connect('exchange_bot.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    phone TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    amount REAL,
    detail TEXT,
    status TEXT,
    time TEXT,
    rate REAL,
    rub_amount REAL
)
""")
conn.commit()


# Состояния бота
class Registration(StatesGroup):
    EnterName = State()
    EnterPhone = State()


class BuyUSDT(StatesGroup):
    EnterAmount = State()
    EnterWallet = State()
    WaitManagerCard = State()
    WaitUserPayment = State()
    WaitManagerConfirm = State()


class SellUSDT(StatesGroup):
    EnterAmount = State()
    EnterCard = State()
    WaitManagerWallet = State()
    WaitUserSend = State()
    WaitManagerConfirm = State()


# Клавиатуры
def get_user_reply_keyboard(is_registered: bool) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📜 Правила")],
        [KeyboardButton(text="💱 Текущий курс")],
    ]

    if not is_registered:
        keyboard.append([KeyboardButton(text="✅ Регистрация")])
    else:
        keyboard.extend([
            [KeyboardButton(text="🛒 Купить USDT")],
            [KeyboardButton(text="💸 Продать USDT")],
            [KeyboardButton(text="📊 Моя статистика")]
        ])

    keyboard.append([KeyboardButton(text="👨‍💼 Связь с менеджером")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Пользователи")],
            [KeyboardButton(text="📊 Статистика (PDF)")],
            [KeyboardButton(text="📥 Скачать БД")],
        ],
        resize_keyboard=True
    )


def get_confirmation_keyboard(user_id: int, action: str) -> InlineKeyboardMarkup:
    if action == "buy":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатил", callback_data=f"paid:{user_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{user_id}")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Перевел USDT", callback_data=f"sent_sell:{user_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_sell:{user_id}")]
        ])

cancel_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить сделку", callback_data="cancel_deal")]
    ]
)



# Утилиты
def user_exists(user_id: int) -> bool:
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone() is not None


# Обработчики команд
@dp.message(F.text == "/start")
async def start(message: Message):
    user_id = message.from_user.id
    is_registered = user_exists(user_id)

    if user_id == ADMIN_ID:
        await message.answer(
            "Добро пожаловать в админ-панель!",
            reply_markup=get_admin_reply_keyboard()
        )
    else:
        if is_registered == False:
            await message.answer(
                "Добро пожаловать! Вы находитесь в надёжном онлайн-обменник криптовалют, где все работает чётко и без лишних вопросов.\n\n💸 Мы занимаемся обменом криптовалют давно и знаем, как важно сохранять спокойствие при любых транзакциях.\n\n⏰ Работаем без выходных - 24/7.\n\n💳 Все операции проводим через карты Таджикских банков - это позволяет избежать блокировки и ограничений по 115-ФЗ.\n\n⬆️ У нас можно легко и быстро купить или продать USDT без лишних комиссий.\n\n🇷🇺 Для клиентов из России:\n- Моментальная выплата на любые банковские карты РФ.\n- Возможность покупки Usdt с карт Т-Банка и Сбербанка.\n\n📊 Всегда актуальный курс, вы можете запросить его в один клик прямо в боте.\n\nДля начала обмена через бота, пожалуйста, пройдите регистрацию, выбрав соответствующую кнопку 'Регистрация' ниже ⬇ ️",
                reply_markup=get_user_reply_keyboard(is_registered)
            )
        if is_registered == True:
            await message.answer(
                "✅ Вы успешно зарегистрированы!\n\nТеперь вам доступны все функции бота-обменника SherExchange!\n\n📜 Правила - Ознакомиться с нашими правилами обмена.\n\n💱 Текущий курс - Узнать текущий курс по которому мы покупаем и продаем USDT\n\n🛒 Купить USDT - Купить USDT на свой кошелек.\n\n💸 Продать USDT - Продать нам USDT и получить деньги на карту.\n\n📊 Моя статистика - Ознакомиться со статистикой своих сделок.\n\n‍💼 Связь с менеджером - Если появились какие-то вопросы, проблемы с оплатой, с получением, что-то не работает, можно связаться с менеджером.\n\n Соответствующие кнопки для работы с ботом ниже⬇️",
                reply_markup=get_user_reply_keyboard(is_registered)
            )


# Регистрация
@dp.message(F.text == "✅ Регистрация")
async def register(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, введите ваше имя:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.EnterName)


@dp.message(Registration.EnterName)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Пожалуйста, введите ваш номер телефона:")
    await state.set_state(Registration.EnterPhone)


@dp.message(Registration.EnterPhone)
async def reg_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    data = await state.get_data()
    cursor.execute(
        "INSERT OR REPLACE INTO users (id, name, phone) VALUES (?, ?, ?)",
        (message.from_user.id, data['name'], phone)
    )
    conn.commit()
    await message.answer(
        "✅ Вы успешно зарегистрированы!\n\nТеперь вам доступны все функции бота-обменника SherExchange!\n\n📜 Правила - Ознакомиться с нашими правилами обмена.\n\n💱 Текущий курс - Узнать текущий курс по которому мы покупаем и продаем USDT\n\n🛒 Купить USDT - Купить USDT на свой кошелек.\n\n💸 Продать USDT - Продать нам USDT и получить деньги на карту.\n\n📊 Моя статистика - Ознакомиться со статистикой своих сделок.\n\n‍💼 Связь с менеджером - Если появились какие-то вопросы, проблемы с оплатой, с получением, что-то не работает, можно связаться с менеджером.\n\n Соответствующие кнопки для работы с ботом ниже⬇️",
        reply_markup=get_user_reply_keyboard(True)
    )
    await state.clear()


# Информационные кнопки
@dp.message(F.text == "📜 Правила")
async def handle_rules(message: Message):
    await message.answer(
        "Покупка:\n\n1. Покупка USDT осуществляется у лиц строго старше 18 лет❗️\n2. Минимальная сумма покупки 100 USDT️❗️\n3. Максимальная сумма покупки 3000 USDT❗️\n\nПродажа:\n\n1. Продажа USDT осуществляется для лиц строго старше 18 лет❗️\n2. Продажа USDT для третьих лиц запрещена❗️\n3. Минимальная сумма продажи 100 USDT❗️\n4. Максимальная сумма продажи 3000 USDT❗️",
        reply_markup=get_user_reply_keyboard(user_exists(message.from_user.id)))


@dp.message(F.text == "💱 Текущий курс")
async def handle_rate(message: Message):
    try:
        buy_rate = await get_usdt_buy_price()
        sell_rate = await get_usdt_sell_price()
        rate_msg = (
            f"💰 <b>Курс обмена:</b>\n\n"
            f"🔼 Купить USDT (вы покупаете у нас): <b>{round(buy_rate * 1.03, 2)} RUB</b>\n"
            f"🔽 Продать USDT (вы продаёте нам): <b>{round(sell_rate * 0.97, 2)} RUB</b>"
        )
        await message.answer(rate_msg, reply_markup=get_user_reply_keyboard(user_exists(message.from_user.id)))
    except Exception as e:
        logging.error(f"Rate error: {e}")
        await message.answer("❗ Не удалось получить курс. Попробуйте позже.")


@dp.message(F.text == "👨‍💼 Связь с менеджером")
async def handle_manager(message: Message):
    await message.answer(f"Свяжитесь с менеджером: {MANAGER_LINK}",
                         reply_markup=get_user_reply_keyboard(user_exists(message.from_user.id)))


@dp.message(F.text == "📊 Моя статистика")
async def handle_user_stats(message: Message):
    user_id = message.from_user.id
    cursor.execute("""
        SELECT type, amount, rub_amount, status, time 
        FROM transactions 
        WHERE user_id = ?
        ORDER BY time DESC
        LIMIT 10
    """, (user_id,))

    transactions = cursor.fetchall()
    if transactions:
        text = "📊 Ваши последние сделки:\n\n"
        for t in transactions:
            rub_amount = f" ({t[2]} RUB)" if t[2] else ""
            text += f"{t[4]}: {t[0]} {t[1]} USDT{rub_amount} ({t[3]})\n"
    else:
        text = "У вас пока нет завершенных сделок."

    await message.answer(text, reply_markup=get_user_reply_keyboard(True))


# Покупка USDT
@dp.message(F.text == "🛒 Купить USDT")
async def buy_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите сумму покупки в USDT (от 100 USDT до 3000 USDT):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BuyUSDT.EnterAmount)


@dp.message(BuyUSDT.EnterAmount)
async def buy_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if not 100 <= amount <= 3000:
            raise ValueError

        # Получаем текущий курс с учетом 3% комиссии
        buy_rate = await get_usdt_buy_price()
        rub_amount = round(amount * buy_rate * 1.03, 2)

        await state.update_data(amount=amount, rub_amount=rub_amount, rate=buy_rate)
        await message.answer(f"💰 Сумма к оплате: {rub_amount} RUB\n\nВведите ваш USDT-кошелек:", reply_markup=cancel_keyboard)
        await state.set_state(BuyUSDT.EnterWallet)
    except ValueError:
        await message.answer("❗ Сумма должна быть от 100 до 3000 USDT. Попробуйте снова.")
    except Exception as e:
        logging.error(f"Buy amount error: {e}")
        await message.answer("❗ Ошибка обработки суммы. Попробуйте снова.")


@dp.message(BuyUSDT.EnterWallet)
async def buy_wallet(message: Message, state: FSMContext):
    wallet = message.text.strip()
    data = await state.get_data()
    amount = data['amount']
    rub_amount = data['rub_amount']
    rate = data['rate']
    user = message.from_user
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "INSERT INTO transactions (user_id, type, amount, detail, status, time, rate, rub_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user.id, 'buy', amount, wallet, 'pending', now, rate, rub_amount)
    )
    conn.commit()

    try:
        await bot.send_message(
            MANAGER_ID,
            f"📥 Покупка {amount} USDT\nКошелек: {wallet}\nСумма к оплате: {rub_amount} RUB\nКурс: {rate} RUB/USDT\nПользователь: {user.full_name} ({user.id})\n\n"
            f"🔁 Ответьте на это сообщение номером карты для оплаты",
            parse_mode=None
        )
        await message.answer("✅ Заявка отправлена менеджеру. Ожидайте реквизиты для перевода.")
        await state.set_state(BuyUSDT.WaitManagerCard)
    except Exception as e:
        logging.error(f"Manager notification error: {e}")
        await message.answer("❗ Не удалось связаться с менеджером. Попробуйте позже.")
        await state.clear()


# Продажа USDT
@dp.message(F.text == "💸 Продать USDT")
async def sell_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите сумму продажи в USDT (от 100 USDT до 3000 USDT):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(SellUSDT.EnterAmount)


@dp.message(SellUSDT.EnterAmount)
async def sell_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if not 100 <= amount <= 3000:
            raise ValueError

        # Получаем текущий курс продажи
        sell_rate = await get_usdt_sell_price()
        rub_amount = round(amount * sell_rate * 1.03, 2)

        await state.update_data(amount=amount, rub_amount=rub_amount, rate=sell_rate)
        await message.answer(f"💰 Вы получите: {rub_amount} RUB\n\nВведите номер банковской карты для получения RUB:\nНомер карты одним числом (16 цифр) без пробелов❗️", reply_markup=cancel_keyboard)
        await state.set_state(SellUSDT.EnterCard)

    except ValueError:
        await message.answer("❗ Сумма должна быть от 100 до 3000 USDT. Попробуйте снова.")
    except Exception as e:
        logging.error(f"Sell amount error: {e}")
        await message.answer("❗ Ошибка обработки суммы. Попробуйте снова.")


@dp.message(SellUSDT.EnterCard)
async def sell_card(message: Message, state: FSMContext):
    try:
        card = message.text.strip()
        if not card or len(card) < 16:
            await message.answer("❗ Введите корректный номер карты (минимум 16 цифр) без пробелов")
            return

        data = await state.get_data()
        amount = data['amount']
        rub_amount = data['rub_amount']
        rate = data['rate']
        user = message.from_user
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            "INSERT INTO transactions (user_id, type, amount, detail, status, time, rate, rub_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user.id, 'sell', amount, card, 'pending', now, rate, rub_amount)
        )
        conn.commit()

        await bot.send_message(
            MANAGER_ID,
            f"📤 Продажа {amount} USDT\nСумма к выплате: {rub_amount} RUB\nКурс: {rate} RUB/USDT\nКарта: {card}\nПользователь: {user.full_name} ({user.id})\n\n"
            f"🔁 Ответьте на это сообщение USDT-кошельком для перевода",
            parse_mode=None
        )

        await message.answer("✅ Заявка отправлена менеджеру. Ожидайте реквизиты для перевода.")
        await state.set_state(SellUSDT.WaitManagerWallet)

    except Exception as e:
        logging.error(f"Sell card error: {e}")
        await message.answer("❗ Ошибка обработки заявки. Попробуйте снова.")
        await state.clear()


# Обработчик ответов менеджера
@dp.message(F.reply_to_message, F.from_user.id == MANAGER_ID)
async def handle_manager_reply(message: Message):
    reply_msg = message.reply_to_message.text

    try:
        if "Покупка" in reply_msg:
            card = message.text.strip()
            user_id = int(reply_msg.split("Пользователь: ")[1].split("(")[1].split(")")[0])

            # Получаем данные о транзакции
            cursor.execute(
                "SELECT amount, rub_amount FROM transactions WHERE user_id = ? AND status = 'pending' AND type = 'buy' ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            transaction = cursor.fetchone()
            if not transaction:
                await message.reply("❗ Не найдена активная заявка на покупку.")
                return

            amount, rub_amount = transaction

            await bot.send_message(
                user_id,
                f"💳 Оплатите {rub_amount} RUB по реквизитам:\n<code>{card}</code>\n\n"
                f"После оплаты нажмите кнопку ниже:",
                reply_markup=get_confirmation_keyboard(user_id, "buy"),
                parse_mode=ParseMode.HTML
            )
            await message.reply("✅ Реквизиты отправлены пользователю.")

        elif "Продажа" in reply_msg:
            wallet = message.text.strip()
            user_id = int(reply_msg.split("Пользователь: ")[1].split("(")[1].split(")")[0])

            # Получаем данные о транзакции
            cursor.execute(
                "SELECT amount, rub_amount FROM transactions WHERE user_id = ? AND status = 'pending' AND type = 'sell' ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            transaction = cursor.fetchone()
            if not transaction:
                await message.reply("❗ Не найдена активная заявка на продажу.")
                return

            amount, rub_amount = transaction

            await bot.send_message(
                user_id,
                f"📤 Переведите {amount} USDT на кошелек:\n<code>{wallet}</code>\n\n"
                f"Вы получите: {rub_amount} RUB\n\n"
                f"После перевода нажмите кнопку ниже:",
                reply_markup=get_confirmation_keyboard(user_id, "sell"),
                parse_mode=ParseMode.HTML
            )
            await message.reply("✅ Реквизиты отправлены пользователю.")

    except Exception as e:
        logging.error(f"Manager reply error: {e}")
        await message.reply("❗ Ошибка обработки запроса. Проверьте формат.")


@dp.callback_query(F.data.startswith("paid:"))
async def paid_confirm(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    # Получаем данные о сделке: RUB, сумма USDT и кошелёк
    cursor.execute("""
        SELECT amount, rub_amount, detail FROM transactions 
        WHERE user_id = ? AND status = 'pending' AND type = 'buy'
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    result = cursor.fetchone()

    if not result:
        await callback.message.edit_text("❗ Не найдена активная сделка.")
        return

    usdt_amount, rub_amount, wallet = result

    await bot.send_message(
        MANAGER_ID,
        f"💸 Пользователь <code>{user_id}</code> подтвердил оплату на сумму <b>{rub_amount} RUB</b>:\n\n"
        f"🔍 Внимательно проверьте получение средств.\n"
        f"Если оплата получена, переведите <b>{usdt_amount} USDT</b>\n"
        f"на кошелёк пользователя:\n<code>{wallet}</code>\n\n"
        f"Затем подтвердите или отклоните сделку по кнопкам ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить платеж", callback_data=f"confirm:{user_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline:{user_id}")]
        ]),
        parse_mode=ParseMode.HTML
    )

    await callback.message.edit_text("⏳ Ожидайте подтверждения менеджера.")
    await callback.answer()


@dp.callback_query(F.data.startswith("sent_sell:"))
async def sent_sell_confirm(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute("""
        SELECT amount, rub_amount, detail FROM transactions 
        WHERE user_id = ? AND status = 'pending' AND type = 'sell'
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    result = cursor.fetchone()

    if not result:
        await callback.message.edit_text("❗ Не найдена активная сделка.")
        return

    usdt_amount, rub_amount, card_number = result

    await bot.send_message(
        MANAGER_ID,
        f"💸 Пользователь <code>{user_id}</code> подтвердил перевод <b>{usdt_amount} USDT</b>\n"
        f"на кошелёк, который вы отправили ранее:\n\n"
        f"🔍 Если средства получены, переведите <b>{rub_amount} RUB</b>\n"
        f"на карту пользователя:\n<code>{card_number}</code>\n\n"
        f"Затем подтвердите или отклоните сделку по кнопкам ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить перевод", callback_data=f"confirm_sell:{user_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_sell:{user_id}")]
        ]),
        parse_mode=ParseMode.HTML
    )

    await callback.message.edit_text("⏳ Ожидайте подтверждения менеджера.")
    await callback.answer()



# Завершение сделок
@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_buy(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute(
        "UPDATE transactions SET status = 'completed' WHERE user_id = ? AND status = 'pending' AND type = 'buy'",
        (user_id,)
    )
    conn.commit()

    await bot.send_message(
        user_id,
        "✅ Сделка завершена! USDT зачислены на ваш кошелек.",
        reply_markup=get_user_reply_keyboard(True)
    )
    await callback.message.edit_text("✅ Покупка подтверждена.")
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_sell:"))
async def confirm_sell(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute(
        "UPDATE transactions SET status = 'completed' WHERE user_id = ? AND status = 'pending' AND type = 'sell'",
        (user_id,)
    )
    conn.commit()

    await bot.send_message(
        user_id,
        "✅ Сделка завершена! RUB будут зачислены на вашу карту.",
        reply_markup=get_user_reply_keyboard(True)
    )
    await callback.message.edit_text("✅ Продажа подтверждена.")
    await callback.answer()


# Отмена сделок
@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_buy(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute(
        "UPDATE transactions SET status = 'cancelled' WHERE user_id = ? AND status = 'pending' AND type = 'buy'",
        (user_id,)
    )
    conn.commit()

    await bot.send_message(
        user_id,
        "❌ Сделка отменена.",
        reply_markup=get_user_reply_keyboard(True)
    )
    await bot.send_message(MANAGER_ID, f"🚫 Пользователь {user_id} отменил покупку.")
    await callback.message.edit_text("❌ Сделка отменена.")
    await callback.answer()


@dp.callback_query(F.data.startswith("cancel_sell:"))
async def cancel_sell(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute(
        "UPDATE transactions SET status = 'cancelled' WHERE user_id = ? AND status = 'pending' AND type = 'sell'",
        (user_id,)
    )
    conn.commit()

    await bot.send_message(
        user_id,
        "❌ Сделка отменена.",
        reply_markup=get_user_reply_keyboard(True)
    )
    await bot.send_message(MANAGER_ID, f"🚫 Пользователь {user_id} отменил продажу.")
    await callback.message.edit_text("❌ Сделка отменена.")
    await callback.answer()


# Отклонение подтверждения
@dp.callback_query(F.data.startswith("decline:"))
async def decline_payment(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute(
        "UPDATE transactions SET status = 'failed' WHERE user_id = ? AND status = 'pending' AND type = 'buy'",
        (user_id,)
    )
    conn.commit()

    await bot.send_message(
        user_id,
        f"❌ Платёж не подтверждён администратором. Пожалуйста, свяжитесь с менеджером: {MANAGER_LINK}",
        reply_markup=get_user_reply_keyboard(True)
    )
    await callback.message.edit_text("❌ Платёж отклонён. Пользователь уведомлён.")
    await callback.answer()


@dp.callback_query(F.data.startswith("decline_sell:"))
async def decline_sell(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    cursor.execute(
        "UPDATE transactions SET status = 'failed' WHERE user_id = ? AND status = 'pending' AND type = 'sell'",
        (user_id,)
    )
    conn.commit()

    await bot.send_message(
        user_id,
        f"❌ Перевод не подтверждён! Пожалуйста, свяжитесь с менеджером: {MANAGER_LINK}",
        reply_markup=get_user_reply_keyboard(True)
    )
    await callback.message.edit_text("❌ Продажа отклонена. Пользователь уведомлён.")
    await callback.answer()

@dp.callback_query(F.data == "cancel_deal")
async def cancel_current_deal(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Сделка отменена. ",
        reply_markup=None
    )
    await callback.message.answer(
        "Вы вернулись в главное меню:",
        reply_markup=get_user_reply_keyboard(user_exists(callback.from_user.id))
    )
    await callback.answer()


# Админ панель
@dp.message(F.text == "📋 Пользователи")
async def admin_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    text = "👥 Пользователи:\n\n" + "\n".join(
        f"ID: {u[0]}, Имя: {u[1]}, Телефон: {u[2]}" for u in users
    ) if users else "Нет пользователей."
    await message.answer(text)


@dp.message(F.text == "📊 Статистика (PDF)")
async def admin_stats_pdf(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    try:
        filename = generate_stats_pdf()

        if os.path.exists(filename):
            await message.answer_document(
                FSInputFile(filename),
                caption="📊 Отчет по сделкам"
            )
            os.remove(filename)
        else:
            await message.answer("❌ Не удалось сгенерировать отчет")

    except Exception as e:
        logging.error(f"PDF generation error: {e}")
        await message.answer("❌ Ошибка при генерации отчета")


@dp.message(F.text == "📥 Скачать БД")
async def admin_db(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return

    file = FSInputFile("exchange_bot.db")
    await message.answer_document(file, caption="📥 База данных")


def generate_stats_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('Roboto', '', 'Roboto.ttf', uni=True)
    pdf.set_font('Roboto', '', 9)

    pdf.cell(200, 10, txt="Отчет по сделкам", ln=1, align='C')
    pdf.cell(200, 10, txt=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ln=1, align='C')
    pdf.ln(10)

    cursor.execute("""
        SELECT t.id, u.id, u.name, u.phone, t.type, t.amount, t.rub_amount, t.status, t.time 
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.time DESC
    """)
    transactions = cursor.fetchall()

    pdf.set_fill_color(200, 220, 255)
    pdf.cell(15, 10, "ID", 1, 0, 'C', True)
    pdf.cell(20, 10, "User ID", 1, 0, 'C', True)
    pdf.cell(30, 10, "Имя", 1, 0, 'C', True)
    pdf.cell(30, 10, "Телефон", 1, 0, 'C', True)
    pdf.cell(20, 10, "Тип", 1, 0, 'C', True)
    pdf.cell(25, 10, "USDT", 1, 0, 'C', True)
    pdf.cell(25, 10, "RUB", 1, 0, 'C', True)
    pdf.cell(25, 10, "Статус", 1, 0, 'C', True)
    pdf.cell(30, 10, "Время", 1, 1, 'C', True)

    for t in transactions:
        if t[7] == 'completed':
            pdf.set_text_color(0, 128, 0)
        elif t[7] == 'cancelled':
            pdf.set_text_color(255, 0, 0)
        else:
            pdf.set_text_color(0, 0, 0)

        pdf.cell(15, 10, str(t[0]), 1)
        pdf.cell(20, 10, str(t[1]), 1)
        pdf.cell(30, 10, t[2][:20] if t[2] else "-", 1)
        pdf.cell(30, 10, t[3] if t[3] else "-", 1)
        pdf.cell(20, 10, t[4], 1)
        pdf.cell(25, 10, str(t[5]), 1)
        pdf.cell(25, 10, str(t[6]) if t[6] else "-", 1)
        pdf.cell(25, 10, t[7], 1)
        pdf.cell(30, 10, t[8][:16], 1, 1)
        pdf.set_text_color(0, 0, 0)

    pdf.ln(10)
    pdf.set_font('Roboto', '', 12)

    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'completed'")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'cancelled'")
    cancelled = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE status = 'completed' AND type = 'buy'")
    total_buy = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(rub_amount) FROM transactions WHERE status = 'completed' AND type = 'buy'")
    total_buy_rub = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE status = 'completed' AND type = 'sell'")
    total_sell = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(rub_amount) FROM transactions WHERE status = 'completed' AND type = 'sell'")
    total_sell_rub = cursor.fetchone()[0] or 0

    pdf.cell(0, 10, f"Всего сделок: {completed + cancelled + pending}", ln=1)
    pdf.cell(0, 10, f"Завершено: {completed}", ln=1)
    pdf.cell(0, 10, f"Отменено: {cancelled}", ln=1)
    pdf.cell(0, 10, f"В ожидании: {pending}", ln=1)
    pdf.cell(0, 10, f"Всего куплено USDT: {total_buy} (на {total_buy_rub} RUB)", ln=1)
    pdf.cell(0, 10, f"Всего продано USDT: {total_sell} (на {total_sell_rub} RUB)", ln=1)

    filename = f"transactions_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    return filename


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
