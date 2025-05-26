import aiohttp
import asyncio
import json
import logging
from typing import Optional


class YandexGPTClient:
    def __init__(self, api_key: str, folder_id: str):
        """
        Инициализация клиента YandexGPT
        api_key: API ключ Yandex Cloud
        folder_id: ID папки в Yandex Cloud
        """
        self.api_key = api_key
        self.folder_id = folder_id
        self.session = None
        self.base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1"

    async def initialize(self):
        """Инициализация сессии"""
        self.session = aiohttp.ClientSession()
        logging.info("✅ YandexGPT клиент инициализирован")

    async def get_response(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        Получение ответа от YandexGPT
        prompt: текст запроса
        max_retries: количество попыток при ошибке
        """
        if not self.session:
            logging.error("❌ YandexGPT не инициализирован")
            return None

        url = f"{self.base_url}/completion"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.api_key}"
        }

        payload = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": 1000
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }

        for attempt in range(max_retries):
            try:
                logging.info(f"🤖 Отправка запроса в YandexGPT (попытка {attempt + 1})")

                async with self.session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()

                        if "result" in result and "alternatives" in result["result"]:
                            alternatives = result["result"]["alternatives"]
                            if alternatives and len(alternatives) > 0:
                                content = alternatives[0]["message"]["text"]
                                logging.info("✅ Получен ответ от YandexGPT")
                                return content.strip()

                        logging.warning("⚠️ Пустой ответ от YandexGPT")
                        return None

                    elif response.status == 401:
                        logging.error("❌ Ошибка авторизации YandexGPT. Проверьте API ключ")
                        return None

                    elif response.status == 403:
                        logging.error("❌ Нет доступа к YandexGPT. Проверьте folder_id и права доступа")
                        return None

                    else:
                        error_text = await response.text()
                        logging.error(f"❌ Ошибка YandexGPT API: {response.status} - {error_text}")

                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                            continue

                        return None

            except asyncio.TimeoutError:
                logging.warning(f"⏰ Таймаут запроса к YandexGPT (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                return None

            except Exception as e:
                logging.error(f"❌ Ошибка при запросе к YandexGPT: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                return None

        logging.error("❌ Все попытки запроса к YandexGPT исчерпаны")
        return None

    async def close(self):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
            logging.info("🔐 Сессия YandexGPT закрыта")