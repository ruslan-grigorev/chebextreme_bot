import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime
from typing import Dict, List, Optional


class GoogleSheetsClient:
    def __init__(self, credentials_file: str, spreadsheet_id: str):
        """
        Инициализация клиента Google Sheets
        credentials_file: путь к JSON файлу с учетными данными сервисного аккаунта
        spreadsheet_id: ID Google Таблицы (из URL)
        """
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.sheet = None

    async def initialize(self):
        """Инициализация подключения к Google Sheets"""
        try:
            # Области доступа
            scope = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]

            # Создаем учетные данные
            credentials = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=scope
            )

            # Создаем клиент
            self.client = gspread.authorize(credentials)

            # Открываем таблицу
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)

            # Получаем или создаем лист "Бронирования"
            try:
                self.sheet = spreadsheet.worksheet("Бронирования")
            except gspread.WorksheetNotFound:
                # Создаем новый лист если не существует
                self.sheet = spreadsheet.add_worksheet(
                    title="Бронирования",
                    rows="1000",
                    cols="20"
                )
                # Добавляем заголовки
                headers = [
                    "Дата бронирования", "Telegram ID", "Username", "ФИО",
                    "Телефон", "Серия паспорта", "Номер паспорта", "Дата рождения",
                    "Мероприятие", "Стоимость", "Статус оплаты", "Примечания"
                ]
                self.sheet.append_row(headers)

            logging.info("✅ Google Sheets подключены")

        except Exception as e:
            logging.error(f"❌ Ошибка подключения к Google Sheets: {e}")
            raise

    def add_booking(self, booking_data: Dict) -> bool:
        """
        Добавление бронирования в таблицу
        booking_data: словарь с данными бронирования
        """
        try:
            now = datetime.now().strftime("%d.%m.%Y %H:%M")

            row_data = [
                now,  # Дата бронирования
                str(booking_data.get('telegram_id', '')),
                booking_data.get('username', ''),
                booking_data.get('full_name', ''),
                booking_data.get('phone', ''),
                booking_data.get('passport_series', ''),
                booking_data.get('passport_number', ''),
                booking_data.get('birth_date', ''),
                booking_data.get('event_name', ''),
                booking_data.get('price', ''),
                booking_data.get('payment_status', 'Не оплачено'),
                booking_data.get('notes', '')
            ]

            self.sheet.append_row(row_data)
            logging.info(f"✅ Бронирование добавлено для {booking_data.get('full_name')}")
            return True

        except Exception as e:
            logging.error(f"❌ Ошибка добавления бронирования: {e}")
            return False

    def get_user_bookings(self, telegram_id: int) -> List[Dict]:
        """Получение всех бронирований пользователя"""
        try:
            all_records = self.sheet.get_all_records()
            user_bookings = [
                record for record in all_records
                if str(record.get('Telegram ID')) == str(telegram_id)
            ]
            return user_bookings

        except Exception as e:
            logging.error(f"❌ Ошибка получения бронирований: {e}")
            return []

    def update_payment_status(self, telegram_id: int, event_name: str, status: str) -> bool:
        """Обновление статуса оплаты бронирования"""
        try:
            all_records = self.sheet.get_all_values()

            for i, row in enumerate(all_records[1:], start=2):  # Начинаем с 2 строки (пропускаем заголовки)
                if (str(row[1]) == str(telegram_id) and
                        row[8] == event_name and
                        row[10] != "Оплачено"):
                    self.sheet.update_cell(i, 11, status)  # Колонка "Статус оплаты"
                    logging.info(f"✅ Статус оплаты обновлен для {telegram_id}")
                    return True

            return False

        except Exception as e:
            logging.error(f"❌ Ошибка обновления статуса: {e}")
            return False