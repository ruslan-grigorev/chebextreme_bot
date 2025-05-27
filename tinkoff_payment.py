import uuid
import requests
import os
import hashlib
import logging
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Загружаем переменные окружения
logger.debug("Загружаем переменные окружения из .env файла")
load_dotenv(override=True)  # Принудительная перезагрузка

# Конфигурация Tinkoff
TINKOFF_TERMINAL_KEY = os.getenv("TINKOFF_TERMINAL_KEY")
TINKOFF_SECRET_KEY = os.getenv("TINKOFF_SECRET_KEY")
if not TINKOFF_SECRET_KEY:
    raise ValueError("TINKOFF_SECRET_KEY не настроен")
# Используем тестовый URL для API
TINKOFF_API_URL = "https://securepay.tinkoff.ru/v2"

# Заголовки для запросов
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

# Отладочный вывод значений
logger.debug(f"Текущая директория: {os.getcwd()}")
logger.debug(f"TINKOFF_TERMINAL_KEY: {TINKOFF_TERMINAL_KEY}")
logger.debug(f"TINKOFF_SECRET_KEY: {TINKOFF_SECRET_KEY}")
logger.debug(f"TINKOFF_API_URL: {TINKOFF_API_URL}")

# URL'ы для редиректа (можно настроить через переменные окружения)
SUCCESS_URL = os.getenv("TINKOFF_SUCCESS_URL", "https://t.me/chebextreme")
FAIL_URL = os.getenv("TINKOFF_FAIL_URL", "https://t.me/chebextreme")

# Словарь для хранения информации о платежах
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

def generate_token(data: dict, secret_key: str) -> str:
    # Исключаем Token, Receipt, DATA
    data_for_token = {
        k: v for k, v in data.items() 
        if k != "Token" and v is not None and k not in ["Receipt", "DATA"]
    }

    sorted_pairs = sorted(data_for_token.items())

    logger.debug(f"Sorted pairs for token: {sorted_pairs}")

    values = []
    for key, value in sorted_pairs:
        if isinstance(value, bool):
            values.append("true" if value else "false")
        elif isinstance(value, (int, float)):
            values.append(str(int(value)))
        else:
            values.append(str(value))

    values.append(str(secret_key))

    token_str = "".join(values)
    logger.debug(f"Token string before hash: {token_str}")

    return hashlib.sha256(token_str.encode('utf-8')).hexdigest()



def init_payment(amount: int, description: str, customer_id: str,
                 customer_email: str = None, customer_phone: str = None,
                 chat_id: int = None) -> str:
    """
    Инициализация платежа через Tinkoff API
    """
    if not TINKOFF_TERMINAL_KEY or not TINKOFF_SECRET_KEY:
        raise Exception("Не настроены ключи Tinkoff API")

    if amount < 1:
        raise ValueError("Сумма должна быть не менее 1 рубля")
    
    logger.debug(f"Amount (руб): {amount}, Amount (копейки): {amount * 100}")

    order_id = str(uuid.uuid4())
    logger.debug(f"Generated OrderId: {order_id}")

    # Сохраняем информацию о платеже для последующей обработки webhook'ом
    if chat_id:
        save_payment_info(order_id, chat_id, amount)

    # Базовый payload
    payload = {
        "TerminalKey": TINKOFF_TERMINAL_KEY,
        "Amount": amount * 100,  # Конвертируем рубли в копейки
        "OrderId": order_id,
        "Description": description,
    }

    # Добавляем данные клиента если есть
    if customer_email or customer_phone:
        payload["DATA"] = {}
        if customer_email:
            payload["DATA"]["Email"] = customer_email
        if customer_phone:
            payload["DATA"]["Phone"] = customer_phone

    # Генерируем токен
    payload["Token"] = generate_token(payload, TINKOFF_SECRET_KEY)

    logger.info(f"Создание платежа на сумму {amount} руб. для клиента {customer_id}")
    logger.debug(f"Payload: {payload}")

    try:
        response = requests.post(
            f"{TINKOFF_API_URL}/Init",
            json=payload,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        logger.debug(f"Ответ от Tinkoff: {data}")

        if data.get("Success"):
            payment_id = data.get("PaymentId")
            payment_url = data.get("PaymentURL")

            logger.info(f"Платеж создан успешно. PaymentId: {payment_id}")
            return payment_url
        else:
            error_message = data.get("Message", "Неизвестная ошибка")
            error_code = data.get("ErrorCode", "")
            details = data.get("Details", "")
            raise Exception(
                f"Ошибка создания платежа: {error_message} "
                f"(код: {error_code}, детали: {details})"
            )

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к Tinkoff API: {e}")
        raise Exception(f"Ошибка связи с платежной системой: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании платежа: {e}")
        raise


def check_payment_status(payment_id: str) -> Dict:
    """
    Проверка статуса платежа
    """
    payload = {
        "TerminalKey": TINKOFF_TERMINAL_KEY,
        "PaymentId": payment_id
    }

    payload["Token"] = generate_token(payload, TINKOFF_SECRET_KEY)

    try:
        response = requests.post(
            f"{TINKOFF_API_URL}/GetState",
            json=payload,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if data.get("Success"):
            return {
                "status": data.get("Status"),
                "payment_id": data.get("PaymentId"),
                "order_id": data.get("OrderId"),
                "amount": data.get("Amount", 0) // 100,
                "success": True
            }
        else:
            return {
                "success": False,
                "error": data.get("Message", "Ошибка получения статуса")
            }

    except Exception as e:
        logger.error(f"Ошибка проверки статуса платежа {payment_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def cancel_payment(payment_id: str) -> bool:
    """
    Отмена платежа
    """
    payload = {
        "TerminalKey": TINKOFF_TERMINAL_KEY,
        "PaymentId": payment_id
    }

    payload["Token"] = generate_token(payload, TINKOFF_SECRET_KEY)

    try:
        response = requests.post(
            f"{TINKOFF_API_URL}/Cancel",
            json=payload,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data.get("Success", False)

    except Exception as e:
        logger.error(f"Ошибка отмены платежа {payment_id}: {e}")
        return False


# Функция для тестирования подключения
def test_connection() -> bool:
    """Тестирование подключения к API Tinkoff"""
    if not TINKOFF_TERMINAL_KEY or not TINKOFF_SECRET_KEY:
        logger.error("Не настроены ключи Tinkoff API")
        return False

    try:
        logger.debug(f"Тестирование подключения с TerminalKey: {TINKOFF_TERMINAL_KEY}")
        logger.debug(f"API URL: {TINKOFF_API_URL}")
        
        # Создаем тестовый платеж
        test_payload = {
            "TerminalKey": TINKOFF_TERMINAL_KEY,
            "Amount": 100,  # 1 рубль
            "OrderId": str(uuid.uuid4()),
            "Description": "Тестовый платеж"
        }
        
        # Генерируем токен
        test_payload["Token"] = generate_token(test_payload, TINKOFF_SECRET_KEY)
        
        logger.debug(f"Тестовый payload: {test_payload}")
        
        response = requests.post(
            f"{TINKOFF_API_URL}/Init",
            json=test_payload,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        logger.debug(f"Ответ от сервера: {data}")
        
        if data.get("Success"):
            logger.info(f"Тест подключения к Tinkoff API прошел успешно. PaymentURL: {data.get('PaymentURL')}")
            return True
        else:
            error_message = data.get("Message", "Неизвестная ошибка")
            error_code = data.get("ErrorCode", "")
            details = data.get("Details", "")
            logger.error(
                f"Тест подключения не прошел: {error_message} "
                f"(код: {error_code}, детали: {details})"
            )
            return False
            
    except Exception as e:
        logger.error(f"Тест подключения к Tinkoff API не прошел: {e}")
        return False
    
if __name__ == "__main__":
    if test_connection():
        logger.info("Тестовое подключение прошло успешно")
    else:
        logger.error("Ошибка при тестовом подключении к Tinkoff API")
        