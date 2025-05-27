from flask import Flask, request, jsonify
import hashlib
import logging
import os
from typing import Dict, Any
import asyncio
from aiogram import Bot
from datetime import datetime
from tinkoff_payment import get_payment_info
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logger = logging.getLogger(__name__)

# Конфигурация
TINKOFF_SECRET_KEY = os.getenv("TINKOFF_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', '0.0.0.0')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 5001))

app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)

# Словарь для хранения информации о платежах
# В реальном приложении это должно быть в базе данных
payment_info = {}

def save_payment_info(order_id: str, chat_id: int, amount: int):
    """Сохранение информации о платеже"""
    payment_info[order_id] = {
        'chat_id': chat_id,
        'amount': amount,
        'created_at': datetime.now().isoformat()
    }

def get_payment_info(order_id: str) -> Dict:
    """Получение информации о платеже"""
    return payment_info.get(order_id, {})

def verify_signature(data: Dict[str, Any], secret_key: str) -> bool:
    """Проверка подписи webhook'а от Tinkoff"""
    if 'Token' not in data:
        return False

    received_token = data.pop('Token')

    # Сортируем данные и создаем строку для хеширования
    sorted_items = sorted(data.items())
    token_str = "".join(str(value) for key, value in sorted_items if key != "Token")
    token_str += secret_key

    calculated_token = hashlib.sha256(token_str.encode('utf-8')).hexdigest()

    # Возвращаем Token обратно в данные
    data['Token'] = received_token

    return calculated_token == received_token

async def handle_payment_notification(payment_data: Dict[str, Any]):
    """Обработка уведомления о платеже"""
    try:
        status = payment_data.get('Status')
        payment_id = payment_data.get('PaymentId')
        order_id = payment_data.get('OrderId')
        amount = payment_data.get('Amount', 0) // 100  # Конвертируем в рубли

        logger.info(f"Получено уведомление о платеже {payment_id}, статус: {status}")
        
        # Получаем информацию о платеже
        payment_info = get_payment_info(order_id)
        chat_id = payment_info.get('chat_id')
        
        if not chat_id:
            logger.error(f"Не найден chat_id для заказа {order_id}")
            return

        if status == 'CONFIRMED':
            # Платеж подтвержден
            await send_payment_success_notification(payment_data, chat_id)
            
        elif status == 'REJECTED':
            # Платеж отклонен
            await send_payment_failed_notification(payment_data, chat_id)
            
        elif status == 'AUTHORIZED':
            # Платеж авторизован, но еще не подтвержден
            await send_payment_authorized_notification(payment_data, chat_id)
            
        elif status == 'REFUNDED':
            # Платеж возвращен
            await send_payment_refunded_notification(payment_data, chat_id)
            
        elif status == 'REVERSED':
            # Платеж отменен
            await send_payment_reversed_notification(payment_data, chat_id)

    except Exception as e:
        logger.error(f"Ошибка обработки уведомления о платеже: {e}")

async def send_payment_success_notification(payment_data: Dict[str, Any], chat_id: int):
    """Отправка уведомления об успешной оплате"""
    try:
        order_id = payment_data.get('OrderId')
        amount = payment_data.get('Amount', 0) // 100

        message = f"""
🎉 *ОПЛАТА ПРОШЛА УСПЕШНО!*

✅ Ваше бронирование подтверждено
💰 Сумма: {amount:,} ₽
📋 Номер заказа: {order_id}

📞 *Что дальше:*
• Мы отправим вам подробную программу мероприятия
• За день до начала мы напомним вам о встрече
• Если у вас есть вопросы, просто ответьте на это сообщение
        """
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об успешной оплате: {e}")

async def send_payment_failed_notification(payment_data: Dict[str, Any], chat_id: int):
    """Отправка уведомления об отклоненной оплате"""
    try:
        order_id = payment_data.get('OrderId')
        amount = payment_data.get('Amount', 0) // 100

        message = f"""
❌ *ОПЛАТА ОТКЛОНЕНА!*
💰 Сумма: {amount:,} ₽
📋 Номер заказа: {order_id}

Пожалуйста, попробуйте еще раз или свяжитесь с поддержкой.
        """
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об отклоненной оплате: {e}")

async def send_payment_authorized_notification(payment_data: Dict[str, Any], chat_id: int):
    """Отправка уведомления об авторизации платежа"""
    try:
        order_id = payment_data.get('OrderId')
        amount = payment_data.get('Amount', 0) // 100

        message = f"""
⏳ *Платеж обрабатывается*
💰 Сумма: {amount:,} ₽
📋 Номер заказа: {order_id}

Мы уведомим вас, когда платеж будет подтвержден.
        """
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об авторизации платежа: {e}")

async def send_payment_refunded_notification(payment_data: Dict[str, Any], chat_id: int):
    """Отправка уведомления о возврате платежа"""
    try:
        order_id = payment_data.get('OrderId')
        amount = payment_data.get('Amount', 0) // 100

        message = f"""
💫 *Возврат платежа выполнен*
💰 Сумма: {amount:,} ₽
📋 Номер заказа: {order_id}

Средства скоро вернутся на ваш счет.
        """
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о возврате платежа: {e}")

async def send_payment_reversed_notification(payment_data: Dict[str, Any], chat_id: int):
    """Отправка уведомления об отмене платежа"""
    try:
        order_id = payment_data.get('OrderId')
        amount = payment_data.get('Amount', 0) // 100

        message = f"""
🔄 *Платеж отменен*
💰 Сумма: {amount:,} ₽
📋 Номер заказа: {order_id}

Если у вас есть вопросы, пожалуйста, свяжитесь с поддержкой.
        """
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об отмене платежа: {e}")

@app.route('/tinkoff_webhook', methods=['POST'])
def tinkoff_webhook():
    """Webhook для получения уведомлений от Tinkoff"""
    data = request.json

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Проверяем подпись
    if not verify_signature(data, TINKOFF_SECRET_KEY):
        logger.warning("Неверная подпись webhook'а")
        return jsonify({"error": "Invalid signature"}), 400

    # Обрабатываем уведомление о платеже
    asyncio.run(handle_payment_notification(data))

    return jsonify({"status": "success"}), 200

@app.route('/')
def index():
    """Простая страница для проверки работы сервера"""
    return "Tinkoff Webhook Server is running!"

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host=WEBHOOK_HOST, port=WEBHOOK_PORT)





