from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re
from datetime import datetime
import logging


# Состояния для машины состояний
class BookingStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_phone = State()
    waiting_for_passport_series = State()
    waiting_for_passport_number = State()
    waiting_for_birth_date = State()
    confirming_booking = State()


# Callback данные для кнопок
class BookingCallback(CallbackData, prefix="book"):
    action: str
    event_id: str = ""


class BookingHandler:
    def __init__(self, sheets_client):
        self.sheets_client = sheets_client

        # Доступные мероприятия
        self.events = {
            "yuryuzan_june": {
                "name": "Сплав по реке Юрюзань",
                "dates": "11-15 июня",
                "location": "Урал",
                "price_early": 18500,
                "price_regular": 19500,
                "early_deadline": "2 июня",
                "description": "Включено: трансфер, питание, прокат группового снаряжения, походная баня, инструктор"
            }
        }

    def get_events_keyboard(self):
        """Клавиатура со списком мероприятий"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for event_id, event in self.events.items():
            button = InlineKeyboardButton(
                text=f"🏕️ {event['name']} ({event['dates']})",
                callback_data=BookingCallback(action="select", event_id=event_id).pack()
            )
            keyboard.inline_keyboard.append([button])

        return keyboard

    def get_confirmation_keyboard(self):
        """Клавиатура подтверждения бронирования"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=BookingCallback(action="confirm").pack()
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=BookingCallback(action="cancel").pack()
                )
            ]
        ])
        return keyboard

    async def start_booking(self, message: Message, state: FSMContext):
        """Начало процесса бронирования"""
        text = """
🎯 **БРОНИРОВАНИЕ МЕРОПРИЯТИЙ**

Выберите мероприятие для бронирования:
"""
        keyboard = self.get_events_keyboard()
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    async def handle_event_selection(self, callback: CallbackQuery, callback_data: BookingCallback, state: FSMContext):
        """Обработка выбора мероприятия"""
        event_id = callback_data.event_id
        event = self.events.get(event_id)

        if not event:
            await callback.answer("❌ Мероприятие не найдено")
            return

        # Сохраняем выбранное мероприятие в состояние
        await state.update_data(selected_event=event_id)

        # Определяем цену
        current_date = datetime.now()
        deadline = datetime.strptime("2024-06-02", "%Y-%m-%d")  # Условная дата для примера
        price = event['price_early'] if current_date < deadline else event['price_regular']

        text = f"""
🏕️ **{event['name']}**
📅 {event['dates']} • 📍 {event['location']}

💰 **Стоимость:** {price:,} ₽
{f"⏰ До {event['early_deadline']} — {event['price_early']:,} ₽" if current_date < deadline else ""}

📋 **Включено:**
{event['description']}

📝 **С собой взять:**
• Личное снаряжение
• Спальник и коврик  
• Личные вещи

---
**Для бронирования мне потребуются ваши данные:**
• ФИО
• Телефон
• Паспортные данные
• Дата рождения

Продолжаем? 👇
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Продолжить бронирование",
                callback_data=BookingCallback(action="start_form").pack()
            )],
            [InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=BookingCallback(action="back").pack()
            )]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()

    async def start_form(self, callback: CallbackQuery, state: FSMContext):
        """Начало заполнения данных"""
        await callback.message.edit_text(
            "📝 **Шаг 1/4: ФИО**\n\n"
            "Введите ваше полное имя (Фамилия Имя Отчество):",
            parse_mode="Markdown"
        )
        await state.set_state(BookingStates.waiting_for_full_name)
        await callback.answer()

    async def process_full_name(self, message: Message, state: FSMContext):
        """Обработка ФИО"""
        full_name = message.text.strip()

        # Простая валидация
        if len(full_name.split()) < 2:
            await message.answer(
                "❌ Пожалуйста, введите полное имя (минимум Фамилия Имя):"
            )
            return

        await state.update_data(full_name=full_name)

        await message.answer(
            "📞 **Шаг 2/4: Телефон**\n\n"
            "Введите ваш номер телефона в формате +7XXXXXXXXXX:",
            parse_mode="Markdown"
        )
        await state.set_state(BookingStates.waiting_for_phone)

    async def process_phone(self, message: Message, state: FSMContext):
        """Обработка телефона"""
        phone = message.text.strip()

        # Валидация телефона
        phone_pattern = r'^(\+7|8)?[0-9]{10}$'
        clean_phone = re.sub(r'[^\d+]', '', phone)

        if not re.match(phone_pattern, clean_phone):
            await message.answer(
                "❌ Неверный формат телефона. Введите в формате +7XXXXXXXXXX или 8XXXXXXXXXX:"
            )
            return

        # Приводим к единому формату
        if clean_phone.startswith('8'):
            clean_phone = '+7' + clean_phone[1:]
        elif not clean_phone.startswith('+7'):
            clean_phone = '+7' + clean_phone

        await state.update_data(phone=clean_phone)

        await message.answer(
            "📄 **Шаг 3/4: Паспорт (серия)**\n\n"
            "Введите серию паспорта (4 цифры):",
            parse_mode="Markdown"
        )
        await state.set_state(BookingStates.waiting_for_passport_series)

    async def process_passport_series(self, message: Message, state: FSMContext):
        """Обработка серии паспорта"""
        series = message.text.strip()

        # Валидация серии паспорта
        if not re.match(r'^\d{4}$', series):
            await message.answer(
                "❌ Серия паспорта должна содержать 4 цифры:"
            )
            return

        await state.update_data(passport_series=series)

        await message.answer(
            "📄 **Шаг 3/4: Паспорт (номер)**\n\n"
            "Введите номер паспорта (6 цифр):",
            parse_mode="Markdown"
        )
        await state.set_state(BookingStates.waiting_for_passport_number)

    async def process_passport_number(self, message: Message, state: FSMContext):
        """Обработка номера паспорта"""
        number = message.text.strip()

        # Валидация номера паспорта
        if not re.match(r'^\d{6}$', number):
            await message.answer(
                "❌ Номер паспорта должен содержать 6 цифр:"
            )
            return

        await state.update_data(passport_number=number)

        await message.answer(
            "📅 **Шаг 4/4: Дата рождения**\n\n"
            "Введите дату рождения в формате ДД.ММ.ГГГГ:",
            parse_mode="Markdown"
        )
        await state.set_state(BookingStates.waiting_for_birth_date)

    async def process_birth_date(self, message: Message, state: FSMContext):
        """Обработка даты рождения"""
        birth_date = message.text.strip()

        # Валидация даты
        try:
            datetime.strptime(birth_date, "%d.%m.%Y")
        except ValueError:
            await message.answer(
                "❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ (например, 15.05.1990):"
            )
            return

        await state.update_data(birth_date=birth_date)

        # Показываем сводку для подтверждения
        await self.show_booking_summary(message, state)

    async def show_booking_summary(self, message: Message, state: FSMContext):
        """Показ сводки для подтверждения"""
        data = await state.get_data()
        event = self.events[data['selected_event']]

        # Определяем цену
        current_date = datetime.now()
        deadline = datetime.strptime("2024-06-02", "%Y-%m-%d")
        price = event['price_early'] if current_date < deadline else event['price_regular']

        summary = f"""
✅ **ПОДТВЕРЖДЕНИЕ БРОНИРОВАНИЯ**

🏕️ **Мероприятие:** {event['name']}
📅 **Даты:** {event['dates']}
📍 **Место:** {event['location']}
💰 **Стоимость:** {price:,} ₽

👤 **Ваши данные:**
• **ФИО:** {data['full_name']}
• **Телефон:** {data['phone']}
• **Паспорт:** {data['passport_series']} {data['passport_number']}
• **Дата рождения:** {data['birth_date']}

---
**Все данные указаны верно?**
"""

        await state.update_data(price=price, event_name=event['name'])
        await state.set_state(BookingStates.confirming_booking)

        keyboard = self.get_confirmation_keyboard()
        await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")

    async def confirm_booking(self, callback: CallbackQuery, state: FSMContext):
        """Подтверждение и сохранение бронирования"""
        data = await state.get_data()
        user = callback.from_user

        # Подготавливаем данные для Google Sheets
        booking_data = {
            'telegram_id': user.id,
            'username': user.username or '',
            'full_name': data['full_name'],
            'phone': data['phone'],
            'passport_series': data['passport_series'],
            'passport_number': data['passport_number'],
            'birth_date': data['birth_date'],
            'event_name': data['event_name'],
            'price': data['price'],
            'payment_status': 'Не оплачено',
            'notes': f"Бронирование через Telegram бота"
        }

        # Сохраняем в Google Sheets
        success = self.sheets_client.add_booking(booking_data)

        if success:
            await callback.message.edit_text(
                f"""
🎉 **БРОНИРОВАНИЕ ПОДТВЕРЖДЕНО!**

Ваша заявка принята и сохранена.
Номер бронирования: #{user.id}{int(datetime.now().timestamp())}

📞 **Что дальше:**
1. Мы свяжемся с вами для подтверждения
2. Отправим реквизиты для оплаты
3. После оплаты пришлем подробную программу

📱 **Остались вопросы?**
Пишите: @chebextreme или +7 927 669 19 52

Спасибо за выбор ChebEXTREME! 🏕️
""",
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ **Ошибка при сохранении бронирования**\n\n"
                "Пожалуйста, обратитесь к администратору:\n"
                "📱 @chebextreme или +7 927 669 19 52",
                parse_mode="Markdown"
            )

        await state.clear()
        await callback.answer()

    async def cancel_booking(self, callback: CallbackQuery, state: FSMContext):
        """Отмена бронирования"""
        await callback.message.edit_text(
            "❌ Бронирование отменено.\n\n"
            "Если передумаете, используйте команду /booking"
        )
        await state.clear()
        await callback.answer()