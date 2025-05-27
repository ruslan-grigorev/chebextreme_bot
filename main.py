import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
import logging
from tinkoff_payment import init_payment

# Попытка загрузить переменные окружения (опционально)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv не установлен. Используйте переменные окружения напрямую.")

from yandex_gpt_client import YandexGPTClient
from knowledge_base import get_context_prompt
from google_sheet_client import GoogleSheetsClient
from booking_handler import BookingHandler, BookingCallback, BookingStates

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токены и настройки (лучше вынести в переменные окружения)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE')
GOOGLE_SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')

# Инициализация бота с хранилищем состояний
storage = MemoryStorage()
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=storage)

# Инициализация клиентов
yandex_gpt = YandexGPTClient(YANDEX_API_KEY, YANDEX_FOLDER_ID)
sheets_client = GoogleSheetsClient(GOOGLE_CREDENTIALS_FILE, GOOGLE_SPREADSHEET_ID)
booking_handler = BookingHandler(sheets_client)

# Словарь для отслеживания активных запросов пользователей
active_requests = set()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = """
🏂 Добро пожаловать в ChebEXTREME!

Мы предоставляем в аренду экстремальное снаряжение и организуем туристические мероприятия:
• Сноуборды и горные лыжи
• Велосипеды
• Электросамокаты
• SUP-борды
• Туристическое снаряжение
• Сплавы и походы

Команды:
/start - 👋 Приветствие и информация о боте
/booking - 🎯 Забронировать мероприятие
/mybookings - 📋 Мои бронирования
/prices - 💰 Цены на прокат
/contact - 📞 Контакты и информация о компании
/help - 🆘 Помощь

Просто задайте мне любой вопрос о наших услугах, ценах или условиях аренды! 🏕️
"""
    await message.answer(welcome_text)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
🆘 Помощь по использованию бота ChebEXTREME

**Команды:**
/start - Приветственное сообщение
/booking - Забронировать мероприятие
/mybookings - Посмотреть свои бронирования
/prices - Показать все цены на прокат
/contact - Показать контакты
/help - Это сообщение

**Бронирование мероприятий:**
• Выберите мероприятие из списка
• Заполните необходимые данные
• Подтвердите бронирование
• Мы свяжемся с вами для оплаты

**Вопросы по прокату:**
Просто напишите свой вопрос, например:
• "Сколько стоит прокат велосипеда на день?"
• "Какие условия аренды SUP-борда?"
• "Есть ли скидки на длительную аренду?"
"""
    await message.answer(help_text)


@dp.message(Command("booking"))
async def cmd_booking(message: Message, state: FSMContext):
    """Команда начала бронирования"""
    await booking_handler.start_booking(message, state)


@dp.message(Command("mybookings"))
async def cmd_my_bookings(message: Message):
    """Просмотр бронирований пользователя"""
    user_id = message.from_user.id
    bookings = sheets_client.get_user_bookings(user_id)

    if not bookings:
        await message.answer(
            "📋 У вас пока нет бронирований.\n\n"
            "Используйте /booking для создания нового бронирования."
        )
        return

    text = "📋 **ВАШИ БРОНИРОВАНИЯ:**\n\n"

    for i, booking in enumerate(bookings, 1):
        text += f"**{i}. {booking.get('Мероприятие', 'Неизвестно')}**\n"
        text += f"💰 {booking.get('Стоимость', 'Не указано')} ₽\n"
        text += f"📅 {booking.get('Дата бронирования', 'Не указано')}\n"
        text += f"💳 {booking.get('Статус оплаты', 'Не указано')}\n"
        text += "---\n"

    text += "\n📞 Вопросы по бронированию: @chebextreme"

    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("prices"))
async def cmd_prices(message: Message):
    prices_text = """
💰 АКТУАЛЬНЫЕ ЦЕНЫ ChebEXTREME

🚴‍♂️ **ВЕЛОСИПЕДЫ:**
Категория «С»: 200₽/ч, 500₽/3ч, 900₽/сутки
Категория «В»: 250₽/ч, 700₽/3ч, 1300₽/сутки  
Категория «А»: 300₽/ч, 900₽/3ч, 2000₽/сутки

🛴 **САМОКАТЫ:** 350₽/ч, 700₽/3ч, 1500₽/сутки

🏄‍♂️ **SUP-БОРДЫ:**
Пн-Чт: 1000₽/сутки
Пт-Вс: 1500₽/сутки

🏕️ **ТУРИСТИЧЕСКОЕ СНАРЯЖЕНИЕ:**
Палатки: от 200₽/сутки
Спальники: от 200₽/сутки
Шатеры: от 1200₽/сутки

🎯 **МЕРОПРИЯТИЯ:**
Сплавы по рекам: от 15000₽
Походы: от 10000₽
Велотуры: от 8000₽

📞 Подробности: /contact или /booking
"""
    await message.answer(prices_text, parse_mode="Markdown")


@dp.message(Command("contact"))
async def cmd_contact(message: Message):
    contact_text = """
📞 **КОНТАКТЫ ChebEXTREME**

🌐 **Сайт:** www.chebextreme.ru
📱 **ВКонтакте:** https://vk.com/chebextremebike
📍 **Город:** Чебоксары
📞 **Телефон:** +7 927 669 19 52
✉️ **Telegram:** @chebextreme

**Режим работы:**
Пн-Пт: 10:00-19:00
Сб-Вс: 10:00-18:00

Пишите в любое время - мы ответим! 🏕️
"""
    await message.answer(contact_text, parse_mode="Markdown")


@dp.message(Command("test_payment"))
async def cmd_test_payment(message: Message):
    """Тестовый платеж"""
    try:
        payment_url = init_payment(
            amount=100,  # 100 рублей
            description="Тестовый платеж",
            customer_id=str(message.from_user.id),
            chat_id=message.from_user.id
        )
        
        await message.answer(
            "💳 Тестовый платеж создан\n\n"
            f"🔗 [Оплатить 100 ₽]({payment_url})",
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


# Обработчики callback'ов для бронирования
@dp.callback_query(BookingCallback.filter())
async def handle_booking_callback(callback: CallbackQuery, callback_data: BookingCallback, state: FSMContext):
    """Обработка callback'ов системы бронирования"""
    action = callback_data.action

    if action == "select":
        await booking_handler.handle_event_selection(callback, callback_data, state)
    elif action == "start_form":
        await booking_handler.start_form(callback, state)
    elif action == "confirm":
        # Получаем данные бронирования
        booking_data = await state.get_data()
        
        try:
            # Создаем платеж в Tinkoff
            payment_url = init_payment(
                amount=int(booking_data.get('amount', 100)),
                 description=f"Бронирование {booking_data.get('event_name') or 'услуги'}",
                customer_id=str(callback.from_user.id),
                chat_id=callback.from_user.id
            )
            
            # Отправляем пользователю ссылку на оплату
            await callback.message.answer(
                "💳 Для завершения бронирования, пожалуйста, оплатите заказ:\n\n"
                f"🎯 Мероприятие: {booking_data.get('event_name')}\n"
                f"💰 Сумма: {booking_data.get('amount')} ₽\n\n"
                f"🔗 Ссылка на оплату: {payment_url}\n\n"
                "После оплаты вы получите подтверждение в этом чате.",
                parse_mode="Markdown"
            )
            
            # Сохраняем бронирование
            await booking_handler.confirm_booking(callback, state)
            
        except Exception as e:
            logging.error(f"Ошибка создания платежа: {e}")
            await callback.message.answer(
                "❌ Произошла ошибка при создании платежа. "
                "Пожалуйста, попробуйте позже или свяжитесь с поддержкой."
            )
            
    elif action == "cancel":
        await booking_handler.cancel_booking(callback, state)
    elif action == "back":
        await booking_handler.start_booking(callback.message, state)


# Обработчики состояний бронирования
@dp.message(BookingStates.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    await booking_handler.process_full_name(message, state)


@dp.message(BookingStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    await booking_handler.process_phone(message, state)


@dp.message(BookingStates.waiting_for_passport_series)
async def process_passport_series(message: Message, state: FSMContext):
    await booking_handler.process_passport_series(message, state)


@dp.message(BookingStates.waiting_for_passport_number)
async def process_passport_number(message: Message, state: FSMContext):
    await booking_handler.process_passport_number(message, state)


@dp.message(BookingStates.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    await booking_handler.process_birth_date(message, state)


@dp.message()
async def handle_message(message: Message, state: FSMContext):
    """Обработка обычных сообщений (вопросы пользователей)"""
    # Проверяем, не находится ли пользователь в процессе бронирования
    current_state = await state.get_state()
    if current_state:
        # Если пользователь в состоянии бронирования, но прислал обычное сообщение
        await message.answer(
            "📝 Вы сейчас заполняете форму бронирования.\n\n"
            "Если хотите прервать бронирование, используйте /start\n"
            "Или продолжите заполнение формы."
        )
        return

    user_id = message.from_user.id

    # Проверяем, есть ли уже активный запрос от этого пользователя
    if user_id in active_requests:
        await message.answer("⏳ Обрабатываю ваш предыдущий запрос, подождите немного...")
        return

    # Добавляем пользователя в активные запросы
    active_requests.add(user_id)

    try:
        # Отправляем сообщение о начале обработки
        processing_msg = await message.answer("🤖 Ищу информацию...")

        # Получаем ответ от YandexGPT
        context_prompt = get_context_prompt(message.text)
        response = await yandex_gpt.get_response(context_prompt)

        if response:
            # Удаляем сообщение о обработке и отправляем ответ
            await processing_msg.delete()

            # Добавляем кнопку бронирования к ответам о мероприятиях
            if any(word in message.text.lower() for word in ['сплав', 'поход', 'мероприятие', 'тур', 'юрюзань']):
                response += "\n\n🎯 Хотите забронировать место? Используйте команду /booking"

            await message.answer(response)
        else:
            await processing_msg.edit_text(
                "😅 Извините, не смог получить ответ от нейросети. "
                "Попробуйте позже или свяжитесь с нами напрямую!\n\n"
                "📞 Контакты: /contact"
            )

    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        await message.answer(
            "😅 Произошла ошибка при обработке запроса. "
            "Попробуйте позже или свяжитесь с нами напрямую!\n\n"
            "📞 Контакты: /contact"
        )

    finally:
        # Убираем пользователя из активных запросов
        active_requests.discard(user_id)


async def main():
    """Запуск бота"""
    logging.info("Запуск бота ChebEXTREME...")

    # Проверяем токены
    if TELEGRAM_TOKEN == 'ваш_телеграм_токен':
        logging.error("❌ Не установлен TELEGRAM_TOKEN!")
        return

    if YANDEX_API_KEY == 'ваш_yandex_api_key':
        logging.error("❌ Не установлен YANDEX_API_KEY!")
        return

    if YANDEX_FOLDER_ID == 'ваш_yandex_folder_id':
        logging.error("❌ Не установлен YANDEX_FOLDER_ID!")
        return

    if GOOGLE_SPREADSHEET_ID == 'ваш_spreadsheet_id':
        logging.error("❌ Не установлен GOOGLE_SPREADSHEET_ID!")
        return

    try:
        # Инициализируем YandexGPT
        await yandex_gpt.initialize()
        logging.info("✅ YandexGPT инициализирован")

        # Инициализируем Google Sheets
        await sheets_client.initialize()
        logging.info("✅ Google Sheets инициализированы")

        # Запускаем бота
        logging.info("🚀 Бот запущен и готов к работе!")
        await dp.start_polling(bot)

    except Exception as e:
        logging.error(f"❌ Ошибка запуска: {e}")

    finally:
        await yandex_gpt.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
    