from os import getenv

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ContentType

from App.Handlers import keyboards as kb
from App.Database import requests as rq


admin_router = Router()
info_command_text = {}


# -------------------------------------------------------------------------------------Управление админа--------------------------------------------------------------------------------------
@admin_router.message(F.text == getenv('ADMIN_SECRET_CODE'))
async def add_admin(message: Message, bot: Bot):
    await message.answer(
        "Siz adminlikka ariza qoldirdingiz. Arizangiz tasdiqlanish jarayonida ⏳",
        reply_markup=kb.uz_to_main_menu_kb
    )
    await bot.send_message(
        chat_id=int(getenv('ADMIN_ID')),
        text=f"<b>Yangi admin qo'shilmoqchi</b>\n\n"
             f"<b>Ismi:</b> {message.from_user.full_name}\n"
             f"<b>ID'si:</b> {message.from_user.id}\n"
             f"<b>Foydalanuvchi nomi:</b> @{message.from_user.username}",
        reply_markup=kb.confirm_admin_kb(message.from_user.id)
    )
    await rq.handle_admin(telegram_id=message.from_user.id, full_name=message.from_user.full_name, username=message.from_user.username)


@admin_router.callback_query(F.data.startswith("admin_confirm"))
async def admin_confirm(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = int(callback.data.split(":")[1])
    admin = await rq.handle_admin(telegram_id=user_id, for_confirm=True)
    await callback.message.answer(
        f"<b>{admin.full_name}</b> adminlikka muvaqqiyatli tasdiqlandi ✅",
        reply_markup=kb.admin_menu_kb
    )
    await bot.send_message(
        chat_id=user_id,
        text=f"Sizning adminlikka arizangiz muvaqqiyatli tasdiqlandi ✅",
        reply_markup=kb.admin_menu_kb
    )


@admin_router.callback_query(F.data.startswith("admin_cancel"))
async def admin_cancel(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = int(callback.data.split(":")[1])
    for_admin_name = await rq.handle_admin(telegram_id=user_id)
    admin_name = for_admin_name.full_name
    await callback.message.answer(
        f"<b>{admin_name}</b> adminlikka muvaqqiyatli bekor qilindi ✅",
        reply_markup=kb.admin_menu_kb
    )
    await bot.send_message(
        chat_id=user_id,
        text=f"Afsuski, sizning adminlikka arizangiz bekor qilindi ❌",
        reply_markup=kb.uz_to_main_menu_kb
    )
    await rq.handle_admin(telegram_id=user_id, for_cancel=True)


# ------------------------------------------------------------------------------------Добавление вопросов-------------------------------------------------------------------------------------
class AddQuestion(StatesGroup):
    enter_ticket_number = State()
    enter_question_text = State()
    enter_first_option = State()
    enter_second_option = State()
    enter_other_options_or_no = State()
    enter_other_options = State()
    choose_correct_option = State()
    send_photo = State()
    confirm_data = State()


class AddTicket(StatesGroup):
    enter_ticket = State()
    confirm_or_reject_ticket = State()


@admin_router.message(F.text.in_(["Savol qo'shish", "Yana savol qo'shish ➕"]))
async def start_add_question(message: Message, state: FSMContext):
    await message.answer("Qaysi bilet uchun savol qo'shmoqchisiz? Bilet sonini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddQuestion.enter_ticket_number)


@admin_router.message(AddQuestion.enter_ticket_number)
async def ticket_input(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Bilet raqami sonda bo'lishi kerak!")
        return

    number = int(message.text)
    ticket = await rq.get_ticket_by_number(number)
    if not ticket:
        await state.clear()
        await message.answer(f"{number}-bilet topilmadi!", reply_markup=kb.ticket_not_found_kb)
        return

    count = await rq.count_questions_in_ticket(ticket.id)
    if count >= 10:
        await message.answer("Bu biletda allaqachon 10 ta savol mavjud.", reply_markup=kb.ticket_not_found_kb)
        return

    await state.update_data(ticket_id=ticket.id, ticket_number=number)
    await message.answer("Yaxshi, endi savolingizni kiriting:")
    await state.set_state(AddQuestion.enter_question_text)


@admin_router.message(AddQuestion.enter_question_text)
async def question_text_input(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Savolni matn sifatida kiriting!")
        return

    await state.update_data(text=message.text, options=[])
    await message.answer("Yaxshi endi variantlarni aniqlab olamiz. Birinchi variantni kiriting:")
    await state.set_state(AddQuestion.enter_first_option)


@admin_router.message(AddQuestion.enter_first_option)
async def add_first_option(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Variantni matn sifatida kiriting!")
        return

    data = await state.get_data()
    options = data.get("options", [])
    options.append(message.text)
    await state.update_data(options=options)

    q_text = data.get("text")
    await message.answer(f"{q_text}\n\nEndi ikkinchi variantni kiriting:",
                             reply_markup=kb.add_first_option_kb(options))
    await state.set_state(AddQuestion.enter_second_option)


@admin_router.message(AddQuestion.enter_second_option)
async def add_second_option(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Variantni matn sifatida kiriting!")
        return

    data = await state.get_data()
    options = data.get("options", [])
    options.append(message.text)
    await state.update_data(options=options)

    q_text = data.get("text")
    await message.answer(f"{q_text}\n\nYaxshi, yana variant qo'shamizmi?\n  • <code>Ha, qo'shamiz</code>\n  • <code>Yo'q, keyingi bosqichga o'tamiz</code>",
                             reply_markup=kb.add_second_option_kb(options))
    await state.set_state(AddQuestion.enter_other_options_or_no)


@admin_router.message(AddQuestion.enter_other_options_or_no)
async def enter_other_options_or_no(message: Message, state: FSMContext):
    data = await state.get_data()
    options = data.get("options", [])
    if message.text == "Ha, qo'shamiz":
        await message.answer("Yangi variantni kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AddQuestion.enter_other_options)
    elif message.text == "Yo'q, keyingi bosqichga o'tamiz":
        await message.answer(f"Chunarli, endi <b>{data.get("text")}</b> savolining to'g'ri javobini tanlang:",
                                      reply_markup=kb.answer_variants_kb(options))
        await state.set_state(AddQuestion.choose_correct_option)
    else:
        await message.answer("Noto'g'ri tanlov. Iltimos, qaytadan javobingizni kiriting ❌")
        return


@admin_router.message(AddQuestion.enter_other_options)
async def add_second_option(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Variantni matn sifatida kiriting!")
        return

    data = await state.get_data()
    options = data.get("options", [])
    options.append(message.text)
    if len(options) >= 5:
        await state.update_data(options=options)

        q_text = data.get("text")
        await message.answer(f"Endi <b>{q_text}</b> savolining to'g'ri javobini tanlang:",
                             reply_markup=kb.answer_variants_kb(options))
        await state.set_state(AddQuestion.choose_correct_option)
    elif len(options) < 5:
        await state.update_data(options=options)

        q_text = data.get("text")
        await message.answer(f"{q_text}\n\nYaxshi, yana variant qo'shamizmi?\n  • <code>Ha, qo'shamiz</code>\n  • <code>Yo'q, keyingi bosqichga o'tamiz</code>",
                                reply_markup=kb.add_other_option_kb(options))
        await state.set_state(AddQuestion.enter_other_options_or_no)


@admin_router.message(AddQuestion.choose_correct_option)
async def select_correct_option(message: Message, state: FSMContext):
    data = await state.get_data()
    options = data.get("options", [])
    text = message.text.strip()

    if text not in options:
        await message.answer("Iltimos, quyidagi variantlardan birini tanlang!")
        return

    await state.update_data(correct_answer=text)

    question_text = data.get("text", "")
    await message.answer(
        f"{question_text}\n\nYaxshi, endi rasm yuboring (majburiy emas):\n\n<code>O'tkazib yuborish</code> — agar rasm yubormoqchi bo'lmasangiz",
        reply_markup=kb.identify_correct_option_kb(options, correct_answer=text)
    )

    await state.set_state(AddQuestion.send_photo)


@admin_router.message(AddQuestion.send_photo, F.text == "O'tkazib yuborish")
async def skip_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(photo_id='-')
    text = data['text']
    options = data['options']
    correct = data['correct_answer']

    await message.answer(f"{text}\n\nZo'r, endi kiritgan ma'lumotlaringizni tasdiqlang",
                         reply_markup=kb.confirm_question_kb(options, correct))
    await state.set_state(AddQuestion.confirm_data)


@admin_router.message(AddQuestion.send_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_id=file_id)

    data = await state.get_data()
    text = data['text']
    options = data['options']
    correct = data['correct_answer']
    await message.answer_photo(
        photo=file_id,
        caption=f"{text}\n\nZo'r, endi kiritgan ma'lumotlaringizni tasdiqlang",
        reply_markup=kb.confirm_question_kb(options, correct)
    )
    await state.set_state(AddQuestion.confirm_data)


@admin_router.callback_query(F.data.in_(["confirm_question", "cancel_question"]))
async def finalize_question(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_id = data.get("photo_id")
    if callback.data == "cancel_question":
        await callback.message.edit_text("Yangi savol muvaffaqiyatli bekor qilindi ❌")
        await state.clear()
        return

    
    await rq.add_question(
        ticket_id=data["ticket_id"],
        text=data["text"],
        options=data["options"],
        correct_answer=data["correct_answer"],
        photo_id=photo_id
    )
    await callback.answer()
    if photo_id == '-':
        await callback.message.delete()
        await callback.message.answer('🎉', reply_markup=kb.after_add_question_kb)
        await callback.message.answer(f"<b>Yangi savol muvaffaqiyatli qo'shildi ✅</b>\n\n<b>Bilet:</b> {data['ticket_number']}\n<b>Savol:</b> {data['text']}",
                                    reply_markup=kb.after_add_question_ikb(data['options'], data['correct_answer']))
        await state.clear()
    elif photo_id != '-':
        await callback.message.delete()
        await callback.message.answer('🎉', reply_markup=kb.after_add_question_kb)
        await callback.message.answer_photo(
            photo=photo_id,
            caption=f"<b>Yangi savol muvaffaqiyatli qo'shildi ✅</b>\n\n<b>Bilet:</b> {data['ticket_number']}\n<b>Savol:</b> {data['text']}",
            reply_markup=kb.after_add_question_ikb(data['options'], data['correct_answer'])
        )
        await state.clear()


@admin_router.message(F.text == "Bilet qo'shish ➕")
async def enter_ticket(message: Message, state: FSMContext):
    await message.answer("Yangi bilet raqamini kiriting <i>(masalan: 1)</i>", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddTicket.enter_ticket)

@admin_router.message(AddTicket.enter_ticket)
async def check_ticket(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Bilet raqami sonda bo'lishi kerak!")
        return
    
    tickets = await rq.get_ticket_by_number(int(message.text))
    if tickets:
        await message.answer("Bunday bilet allaqachon mavjud!", reply_markup=kb.ticket_not_found_kb)
        return
    await state.update_data(ticket_number=int(message.text))
    data = await state.get_data()
    await message.answer(
        f"Siz <b>{data['ticket_number']}</b>-raqamli bilet qo'shmoqchisiz, to'g'rimi?",
        reply_markup=kb.confirm_kb
    )
    await state.set_state(AddTicket.confirm_or_reject_ticket)


@admin_router.message(AddTicket.confirm_or_reject_ticket)
async def confirm_or_reject_ticket(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.strip() == "✅ Tasdiqlash":
        await rq.add_ticket(ticket_num=data['ticket_number'])
        await message.answer(f"<b>{data.get('ticket_number')}</b>-raqamli bilet bazaga muvaffaqiyatli qo'shildi ✅",
                             reply_markup=kb.admin_after_ticket_kb
        )
        await state.clear()
    elif message.text.strip() == "❌ Bekor qilish":
        await message.answer(f"<b>{data.get('ticket_number')}</b>-raqamli bilet muvaffaqiyatli bekor qilindi ❌",
                             reply_markup=kb.admin_to_menu_kb
        )
        await state.clear()
    else:
        await message.answer("Noto'g'ri tanlov. Iltimos, qaytadan tanlang ❌",
                             reply_markup=kb.confirm_kb
        )
        return


# ---------------------------------------------------------------------------------Добавление дорожных знаков----------------------------------------------------------------------------------
class AddRoadSignState(StatesGroup):
    select_type = State()
    enter_sign_name = State()
    enter_sign_description = State()
    send_sign_photo = State()
    check_sign_data = State()


@admin_router.message(F.text.in_({"Yo'l belgisini qo'shish", "Belgi qo'shish ➕"}))
async def add_road_sign(message: Message, state: FSMContext):
    await message.answer(
        "Belgi turini tanlang:",
        reply_markup=kb.admin_road_signs_kb
    )
    await state.set_state(AddRoadSignState.select_type)


@admin_router.message(AddRoadSignState.select_type)
async def select_type(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer(
            "Iltimos, belgi turini matn sifatida kiriting!"
        )
        return


    if message.text.strip() == "❌ Bekor qilish":
        await message.answer(
                "Yo'l belgisini qo'shish jarayoni bekor qilindi ❌",
                reply_markup=kb.admin_to_menu_kb
            )
        await state.clear()
    else:
        await state.update_data(sign_type=message.text)
        await message.answer(
                "Endi belgini nomini kiriting: <i>(masalan: 2.1. Asosiy yo'l)</i>",
                reply_markup=ReplyKeyboardRemove()
            )
        await state.set_state(AddRoadSignState.enter_sign_name)


@admin_router.message(AddRoadSignState.enter_sign_name)
async def enter_sign_name(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer(
            "Iltimos, belgi nomini matn sifatida kiriting!"
        )
        return


    await state.update_data(sign_name=message.text)
    await message.answer(
            "Yaxshi, endi belgi haqida qisqacha ma'lumot bering (majburiy emas):",
            reply_markup=kb.skip_kb
        )
    await state.set_state(AddRoadSignState.enter_sign_description)


@admin_router.message(AddRoadSignState.enter_sign_description)
async def enter_sign_description(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer(
            "Iltimos, belgi ma'lumotini matn sifatida kiriting!"
        )
        return


    if message.text.strip() == "O'tkazib yuborish ⏩":
        await state.update_data(sign_description=None)
        await message.answer(
                "Chunarli, endi belgini rasmini yuboring (majburiy emas):",
                reply_markup=kb.skip_kb
            )
        await state.set_state(AddRoadSignState.send_sign_photo)
    else:
        await state.update_data(sign_description=message.text)
        await message.answer(
                "Oxirgisi, endi belgini rasmini yuboring (majburiy emas):",
                reply_markup=kb.skip_kb
            )
        await state.set_state(AddRoadSignState.send_sign_photo)


@admin_router.message(AddRoadSignState.send_sign_photo, F.text == "O'tkazib yuborish ⏩")
async def skip_sign_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(sign_photo=None)
    await message.answer(
        f"Chunarli, endi bazaga qo'shishdan oldin kiritgan ma'lumotlaringizni tasdiqlang:\n\n"
        f"<b>Belgi rasmi:</b> ❌\n"
        f"<b>Belgi turi:</b> {data.get('sign_type')}\n"
        f"<b>Belgi nomi:</b> {data.get('sign_name')}\n"
        f"<b>Belgi ma'lumoti:</b> {data.get('sign_description') if data.get('sign_description') else '-'}",
        reply_markup=kb.confirm_kb
    )
    await state.set_state(AddRoadSignState.check_sign_data)


@admin_router.message(AddRoadSignState.send_sign_photo, F.photo)
async def handle_sign_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    await state.update_data(sign_photo=file_id)
    await message.answer_photo(
        photo=file_id,
        caption=f"Zo'r, endi bazaga qo'shishdan oldin kiritgan ma'lumotlaringizni tasdiqlang:\n\n"
                f"<b>Belgi turi:</b> {data.get('sign_type')}\n"
                f"<b>Belgi nomi:</b> {data.get('sign_name')}\n"
                f"<b>Belgi ma'lumoti:</b> {data.get('sign_description') if data.get('sign_description') else '-'}",
        reply_markup=kb.confirm_kb
    )
    await state.set_state(AddRoadSignState.check_sign_data)


@admin_router.message(AddRoadSignState.check_sign_data)
async def check_sign_data(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.strip() == "✅ Tasdiqlash":
        await rq.add_road_sign(
            sign_type=data.get('sign_type'),
            sign_name=data.get('sign_name'),
            sign_description=data.get('sign_description'),
            sign_photo=data.get('sign_photo')
        )
        await message.answer(f"<b>{data.get('sign_name')}</b> yo'l belgisi bazaga muvaffaqiyatli qo'shildi ✅",
                             reply_markup=kb.after_checking_sign_kb
        )
        await state.clear()
    elif message.text.strip() == "❌ Bekor qilish":
        await message.answer(f"<b>{data.get('sign_name')}</b> yo'l belgisi muvaffaqiyatli bekor qilindi ❌",
                             reply_markup=kb.after_checking_sign_kb
        )
        await state.clear()
    else:
        await message.answer("Noto'g'ri tanlov. Iltimos, qaytadan tanlang ❌",
                             reply_markup=kb.confirm_kb
        )
        return
    

# ---------------------------------------------------------------------------------Изменение команды info----------------------------------------------------------------------------------
class ChangeInfoCommand(StatesGroup):
    enter_info_text = State()

@admin_router.message(F.text == "Info komandasini o'zgartirish")
async def change_info_command(message: Message, state: FSMContext):
    await message.answer(
        "Iltimos, yangi /info komandasini matn sifatida kiriting:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ChangeInfoCommand.enter_info_text)

@admin_router.message(ChangeInfoCommand.enter_info_text)
async def enter_info_text(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer("Iltimos, matn sifatida kiriting!")
        return

    text_to_save = message.html_text if message.entities else message.text

    await rq.change_info_cmd_text(text_to_save)

    await state.clear()
    await message.answer(
        "✅ /info komandasining matni muvaffaqiyatli yangilandi!",
        reply_markup=kb.admin_to_menu_kb
    )