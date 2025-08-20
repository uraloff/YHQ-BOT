from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)

from App.Database.models import Answer


# -----------------------------------------------------------------------------Клиентские клавиатуры------------------------------------------------------------------------------------------

uz_main_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Real imtihon 20", callback_data='uz_exam')],
    [InlineKeyboardButton(text="Imtihon biletlari", callback_data='uz_tickets')],
    [InlineKeyboardButton(text="Mening statistikam", callback_data='uz_stats')],
    [InlineKeyboardButton(text="Saqlanganlar", callback_data='uz_saved_questions')],
    [InlineKeyboardButton(text="Yo'l belgilari", callback_data='uz_road_signs')]
])


uz_exam_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Boshladik!", callback_data='uz_start_exam')],
    [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data='uz_main_menu')]
])


uz_road_signs_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚠ Ogohlantiruvchi belgilar", callback_data='uz:warning_signs')],
    [InlineKeyboardButton(text="🔶 Imtiyoz belgilari", callback_data='uz:privilege_signs')],
    [InlineKeyboardButton(text="⛔ Ta'qiqlovchi belgilar", callback_data='uz:prohibition_signs')],
    [InlineKeyboardButton(text="⬆ Buyuruvchi belgilar", callback_data='uz:guide_signs')],
    [InlineKeyboardButton(text="🛣 Axborot-ishora belgilari", callback_data='uz:information_signs')],
    [InlineKeyboardButton(text="🛃 Servis belgilari", callback_data='uz:service_signs')],
    [InlineKeyboardButton(text="🔙 Qo'shimcha axborot belgilari", callback_data='uz:additional_information_signs')],
    [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data='uz_main_menu')]
])


def sign_nav_kb(current: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if current > 0:
        kb.button(text="⬅", callback_data="prev_sign")
    if current < total - 1:
        kb.button(text="➡", callback_data="next_sign")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="Yo'l belgilari ro'yxatiga qaytish ↩", callback_data="uz_road_signs"))
    return kb.as_markup()


uz_to_main_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data='uz_main_menu')]
])


def generate_ticket_keyboard(tickets: list[int], current_page: int, per_page: int = 10) -> InlineKeyboardMarkup:
    start = current_page * per_page
    end = start + per_page
    page_tickets = tickets[start:end]

    keyboard = []

    # Разбиваем билеты по рядам (по 5 кнопок в ряд)
    row = []
    for i, ticket_id in enumerate(page_tickets, start=1):
        row.append(InlineKeyboardButton(text=str(ticket_id), callback_data=f"ticket_{ticket_id}"))
        if i % 5 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Стрелки навигации
    total_pages = (len(tickets) - 1) // per_page
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅", callback_data=f"tickets_page_{current_page - 1}"))
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="➡", callback_data=f"tickets_page_{current_page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    # Кнопка "Главное меню"
    keyboard.append([InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="uz_main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_question_keyboard(shuffled_options: list, mode: str, position: int, total_questions: int, session_id: int | None = None, correct_index: int | None = None, answer: Answer | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if mode == "saved":
        for i in range(len(shuffled_options)):
            text = f"F{i+1}"
            if i == correct_index:
                text += " ✅"
            builder.button(
                text=text,
                callback_data="noop"
            )
        builder.adjust(5)

        nav_buttons = []
        if position > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅ Oldingi savol",
                    callback_data=f"saved_question_{position - 1}"
                )
            )
        if position < total_questions - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Keyingi savol ➡",
                    callback_data=f"saved_question_{position + 1}"
                )
            )
        if nav_buttons:
            builder.row(*nav_buttons)

        builder.row(InlineKeyboardButton(text="📤 Saqlanganlardan o'chirish", callback_data=f"remove_saved_question"))
        builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data=f"uz_main_menu"))
    else:
        for i in range(len(shuffled_options)):
            text = f"F{i+1}"
            if answer:
                if shuffled_options[i] == answer.user_answer:
                    text += " ✅" if answer.is_correct else " ❌"
                elif not answer.is_correct and (i+1) == correct_index:
                    text += " ✅"
            builder.button(
                text=text,
                callback_data=f"{mode}_variant_{i}"
            )
        builder.adjust(5)

        nav_buttons = []
        if position > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅ Oldingi savol", callback_data=f"{mode}_question_{position - 1}"))
        if answer:
            if position == total_questions - 1:
                nav_buttons.append(InlineKeyboardButton(text="Test natijalari ➡", callback_data=f"{mode}_test_results"))
            else:    
                nav_buttons.append(InlineKeyboardButton(text="Keyingi savol ➡", callback_data=f"{mode}_question_{position + 1}"))

        if nav_buttons:
            builder.row(*nav_buttons)

        builder.row(InlineKeyboardButton(text="📥 Saqlash", callback_data=f"save_question"),)
        builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data=f"to_main_menu_after_test:{session_id}"))
    
    return builder.as_markup()



def mark_answer_variants_kb(shuffled_options, mode, answer, position, session_id, total_questions, correct_index) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for i in range(len(shuffled_options)):
        text = f"F{i+1}"
        if answer:
            if shuffled_options[i] == answer.user_answer:
                text += " ✅" if answer.is_correct else " ❌"
            elif not answer.is_correct and i == correct_index:
                text += " ✅"
        builder.button(
            text=text,
            callback_data=f"{mode}_variant_{i}"
        )
    builder.adjust(5)

    # Кнопки управления (влево / вправо)
    control_buttons = []
    if position > 0:
        control_buttons.append(InlineKeyboardButton(text="⬅ Oldingi savol", callback_data=f"{mode}_question_{position - 1}"))

    if answer:
        if position == total_questions - 1:  # последний вопрос
            control_buttons.append(InlineKeyboardButton(text="Test natijalari ➡", callback_data=f"{mode}_test_results"))
        else:
            control_buttons.append(InlineKeyboardButton(text="Keyingi savol ➡", callback_data=f"{mode}_question_{position + 1}"))

    if control_buttons:
        builder.row(*control_buttons)
            
    builder.row(InlineKeyboardButton(text="📥 Saqlash", callback_data="save_question"))
    builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data=f"to_main_menu_after_test:{session_id}"))

    return builder.as_markup()


user_question_not_found_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Biletlar bo'limiga qaytish ↩", callback_data="back_to_tickets")],
    [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="uz_main_menu")]
])


uz_stats_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✏ Xatoliklar ustida ishlash", callback_data="uz_mistakes")],
    [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="uz_main_menu")]
])


uz_pass_exam_again_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Ha", callback_data="yes_pass"),
    InlineKeyboardButton(text="❌ Yo'q", callback_data="no_pass")]
])

# -----------------------------------------------------------------------------Админские клавиатуры-------------------------------------------------------------------------------------------
def confirm_admin_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_confirm:{user_id}"),
             InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_cancel:{user_id}")]
    ])


admin_menu_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Savol qo'shish")],
        [KeyboardButton(text="Yo'l belgisini qo'shish")],
        [KeyboardButton(text="Info komandasini o'zgartirish")]
    ],
    resize_keyboard=True
)


admin_to_menu_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Asosiy menyuga qaytish ↩")]
    ],
    resize_keyboard=True
)


admin_after_ticket_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Savol qo'shish")],
        [KeyboardButton(text="Asosiy menyuga qaytish ↩")],
        [KeyboardButton(text="Info komandasini o'zgartirish")]
        ],
    resize_keyboard=True
)


admin_road_signs_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚠ Ogohlantiruvchi belgilar")],
        [KeyboardButton(text="🔶 Imtiyoz belgilari")],
        [KeyboardButton(text="⛔ Ta'qiqlovchi belgilar")],
        [KeyboardButton(text="⬆ Buyuruvchi belgilar")],
        [KeyboardButton(text="🛣 Axborot-ishora belgilari")],
        [KeyboardButton(text="🛃 Servis belgilari")],
        [KeyboardButton(text="🔙 Qo'shimcha axborot belgilari")],
        [KeyboardButton(text="❌ Bekor qilish")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Belgi turini tanlang"
)


confirm_kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="✅ Tasdiqlash"),
             KeyboardButton(text="❌ Bekor qilish")]
    ],
    resize_keyboard=True
)


after_checking_sign_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Belgi qo'shish ➕")],
        [KeyboardButton(text="Asosiy menyuga qaytish ↩")]
    ],
    resize_keyboard=True
)


skip_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="O'tkazib yuborish ⏩")]
    ],
    resize_keyboard=True
)


def answer_variants_kb(options: list[str]) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for i, _ in enumerate(options, start=1):
        kb.button(text=f"F{i}")
    kb.adjust(len(options))
    return kb.as_markup(
        resize_keyboard=True,
        input_field_placeholder="To'g'ri javobni tanlang"
    )


ticket_not_found_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Bilet qo'shish ➕")],
        [KeyboardButton(text="Asosiy menyuga qaytish ↩")]
    ],
    resize_keyboard=True
)


def add_first_option_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text='F1', callback_data="noop")

    kb.adjust(5)
    return kb.as_markup()


def add_second_option_kb(options: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=options[0], callback_data="noop")
    kb.button(text=options[1], callback_data="noop")

    kb.adjust(2)
    return kb.as_markup()


ask_for_other_option_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Ha, qo'shamiz")],
        [KeyboardButton(text="Yo'q, keyingi bosqichga o'tamiz")]
    ],
    resize_keyboard=True
)


def add_other_option_kb(options: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, _ in enumerate(options, start=1):
        kb.button(text=f"F{i}", callback_data="noop")
    kb.adjust(len(options))
    return kb.as_markup()


def identify_correct_option_kb(options: list[str], correct_answer: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for opt in options:
        label = f"{opt} ✅" if opt == correct_answer else opt
        kb.button(text=label, callback_data="noop")
    kb.adjust(len(options))
    return kb.as_markup()


def confirm_question_kb(options: list[str], correct_answer: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for opt in options:
        label = f"{opt} ✅" if opt == correct_answer else opt
        kb.button(text=label, callback_data="noop")
    kb.button(text="Tasdiqlash ✅", callback_data="confirm_question")
    kb.button(text="Bekor qilish ❌", callback_data="cancel_question")
    kb.adjust(len(options), 2)
    return kb.as_markup()


def after_add_question_ikb(options: list[str], correct_answer: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for opt in options:
        label = f"{opt} ✅" if opt == correct_answer else opt
        kb.button(text=label, callback_data="noop")
    kb.adjust(len(options))
    return kb.as_markup()


after_add_question_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Yana savol qo'shish ➕")],
        [KeyboardButton(text="Asosiy menyuga qaytish ↩")]
    ],
    resize_keyboard=True
)