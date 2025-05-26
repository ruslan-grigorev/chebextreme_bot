import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
import logging

# Загрузка .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv не установлен. Используйте переменные окружения напрямую.")

from yandex_gpt_client import YandexGPTClient
from knowledge_base import get_context_prompt

# Логирование
logging.basicConfig(level=logging.INFO)

# Токены
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
yandex_gpt = YandexGPTClient(YANDEX_API_KEY, YANDEX_FOLDER_ID)

active_requests = set()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = """
🏂 Добро пожаловать в ChebEXTREME!

Мы предоставляем в аренду экстремальное снаряжение:
• Сноуборды и горные лыжи
• Велосипеды и электросамокаты  
• SUP-борды, катамараны
• Туристическое снаряжение

Просто задайте вопрос о ценах или условиях аренды, и я помогу! 🏕️
"""
    await message.answer(welcome_text)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
🆘 Помощь по использованию бота ChebEXTREME

Команды:
/start - Приветственное сообщение
/help - Подсказки по использованию
/prices - Показать цены
/contact - Показать контакты

Примеры вопросов:
• Сколько стоит сапборд на выходные?
• Какие условия аренды велосипеда?
• Какие палатки есть?
"""
    await message.answer(help_text)


@dp.message(Command("prices"))
async def cmd_prices(message: Message):
    prices_text = """
💰 АКТУАЛЬНЫЕ ЦЕНЫ ChebEXTREME

🚴‍♂️ ВЕЛОСИПЕДЫ:
Категория «С»: 200₽/ч, 500₽/3ч, 900₽/сутки
Категория «В»: 250₽/ч, 700₽/3ч, 1300₽/сутки  
Категория «А»: 300₽/ч, 900₽/3ч, 2000₽/сутки

🛴 ЭЛЕКТРОСАМОКАТЫ: 350₽/ч, 700₽/3ч, 1500₽/сутки

🏄‍♂️ SUP-БОРДЫ:
Пн–Чт: 1000₽/сутки  
Пт–Вс: 1500₽/сутки (2-е сутки -500₽)

🏕️ ТУРИСТИЧЕСКОЕ СНАРЯЖЕНИЕ:
Палатки: от 200₽, Спальники: от 200₽, Шатры: от 1200₽

📞 Подробнее — /contact
"""
    await message.answer(prices_text)


@dp.message(Command("contact"))
async def cmd_contact(message: Message):
    contact_text = """
📞 КОНТАКТЫ ChebEXTREME

🌐 Сайт: www.chebextreme.ru
📱 Telegram: @chebextreme
📞 Телефон: +7 927 669 19 52
📍 ВКонтакте: https://vk.com/chebextremebike
📍 Город: Чебоксары
"""
    await message.answer(contact_text)


@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id

    if user_id in active_requests:
        await message.answer("⏳ Пожалуйста, подождите. Я ещё обрабатываю ваш предыдущий запрос...")
        return

    active_requests.add(user_id)

    try:
        processing_msg = await message.answer("🤖 Ищу информацию в базе знаний ChebEXTREME...")

        # Сформировать контекстный промпт
        context_prompt = get_context_prompt(message.text)

        # Получить ответ от YandexGPT
        response = await yandex_gpt.get_response(context_prompt)

        if response:
            await processing_msg.delete()
            await message.answer(response.strip())
        else:
            await processing_msg.edit_text(
                "🤷 Я не нашёл точной информации в базе. Пожалуйста, напишите нам напрямую:\n\n📱 /contact"
            )

    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")
        await message.answer("❌ Произошла ошибка при обращении к ИИ. Попробуйте позже или свяжитесь с нами: /contact")

    finally:
        active_requests.discard(user_id)


async def main():
    logging.info("▶️ Запуск ChebEXTREME Bot...")

    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == 'ваш_телеграм_токен':
        logging.error("❌ TELEGRAM_TOKEN не задан")
        return
    if not YANDEX_API_KEY or YANDEX_API_KEY == 'ваш_yandex_api_key':
        logging.error("❌ YANDEX_API_KEY не задан")
        return
    if not YANDEX_FOLDER_ID or YANDEX_FOLDER_ID == 'ваш_yandex_folder_id':
        logging.error("❌ YANDEX_FOLDER_ID не задан")
        return

    try:
        await yandex_gpt.initialize()
        logging.info("✅ YandexGPT инициализирован")

        await dp.start_polling(bot)

    except Exception as e:
        logging.error(f"❌ Ошибка запуска: {e}")

    finally:
        await yandex_gpt.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
