from os import getenv
from datetime import datetime, time, timedelta, timezone

from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto

from App.Database import requests as rq
from App.Handlers import commands, keyboards as kb


uz_user_router = Router()
user_question_cache = {}


# -----------------------------------------------------------------------------------------Главное меню---------------------------------------------------------------------------------------
@uz_user_router.message(F.text.in_({'/start', '/user_mode', '/admin', 'Вернуться на главную меню ↩'}))
@uz_user_router.callback_query(F.data.in_({'uz_main_menu', 'no_pass'}))
@uz_user_router.callback_query(F.data.startswith("to_main_menu_after_test:"))
async def uz_main_menu(message: Message | CallbackQuery, bot: Bot, state: FSMContext):
    await state.clear()
    await commands.set_commands(bot, message.from_user.id)
    await rq.get_or_create_user(telegram_id=message.from_user.id, full_name=message.from_user.full_name, username=message.from_user.username if message.from_user.username else None)
    
    tz = timezone(timedelta(hours=5))
    now = datetime.now(tz).time()

    if time(0, 0) <= now < time(6, 0):
        greeting = "👋 Доброй ночи"
    elif time(6, 0) <= now < time(12, 0):
        greeting = "👋 Доброе утро"
    elif time(12, 0) <= now < time(18, 0):
        greeting = "👋 Добрый день"
    else:
        greeting = "👋 Добрый вечер"
    
    if isinstance(message, Message):
        if ((message.from_user.id == int(getenv('ADMIN_ID')) or await rq.check_confirmed_admin(message.from_user.id)) and (message.text == '/admin' or message.text == 'Вернуться на главную меню ↩')) and not message.text == '/user_mode':
            await message.answer(
                f"{greeting}, <b>{message.from_user.full_name}</b>!",
                reply_markup=kb.admin_menu_kb
            )
        elif (message.from_user.id != int(getenv('ADMIN_ID')) and not await rq.check_confirmed_admin(message.from_user.id)) and message.text == '/admin':
            await message.answer(
                "Siz admin emassiz ❌",
                reply_markup=kb.uz_to_main_menu_kb
            )
        else:
            await message.answer(
                f"👋 Salom, <b>{message.from_user.full_name}</b>! "
                f"Bu bot orqali siz haydovchilik guvohnomasini olish uchun test imtihonlarini yechib tayyorgarlik ko'rishingiz mumkin.\n\n"
                f"👇 Quyidagi kerakli bo'limlarni tanlab hozirdanoq tayyorgarlikni boshlashingiz mumkin",
                reply_markup=kb.uz_main_menu_kb
            )
    else:
        if message.data.startswith('to_main_menu_after_test:'):
            session_id = message.data.split(":")[1]
            session_data = await rq.get_test_session(int(session_id))
            session_has_not_ended = session_data.ended_at is None
            if session_has_not_ended:
                await rq.end_session(int(session_id), message.from_user.id)
        try:
            await message.answer()
            await message.message.edit_text(
                f"<b>🏠 Asosiy menyu\n\n</b>"
                f"👇 Quyidagi kerakli bo'limlarni tanlab hozirdanoq tayyorgarlikni boshlashingiz mumkin",
                reply_markup=kb.uz_main_menu_kb
            )
        except Exception:
            await message.message.delete()
            await message.message.answer(
                f"<b>🏠 Asosiy menyu\n\n</b>"
                f"👇 Quyidagi kerakli bo'limlarni tanlab hozirdanoq tayyorgarlikni boshlashingiz mumkin",
                reply_markup=kb.uz_main_menu_kb
            )
            await message.answer()


# ---------------------------------------------------------------------------------Экзамен----------------------------------------------------------------------------------------------------
@uz_user_router.callback_query(F.data.in_({'uz_exam', 'yes_pass'}))
async def uz_btn_exam(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        f"Imtihonda 20 ta test bo’ladi. 3 ta xato qilsangiz imtihondan yiqilasiz. Omad 😉",
        reply_markup=kb.uz_exam_kb
    )


@uz_user_router.callback_query(F.data == 'uz_start_exam')
async def uz_start_exam(callback: CallbackQuery):
    await callback.answer()
    exam_questions_list = await rq.get_questions('exam')
    if not exam_questions_list:
        await callback.message.edit_text("Imtihon savollari topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        return

    exam_question = exam_questions_list[0]
    session_id = await rq.start_test_session(callback.from_user.id, 'exam', exam_questions_list)
    sq = await rq.get_session_question(session_id, position=0)
    if not sq:
        await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        return
    answer = await rq.get_user_answer(session_id, exam_question.id)

    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>(1/20) {exam_question.question_number}-savol</b>\n\n{exam_question.text}\n\n"]
    for i, opt in enumerate(sq.shuffled_options, start=1):
        lines.append(f"F{i}. {opt}")
        if opt == exam_question.correct_answer:
            correct_index = i
        if i < len(sq.shuffled_options):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=sq.shuffled_options,
        mode='exam',
        position=0,
        total_questions=len(exam_questions_list),
        session_id=session_id,
        correct_index=correct_index,
        answer=answer
    )

    previous_has_photo = callback.message.photo is not None
    new_has_photo = exam_question.photo_id != '-'

    user_question_cache[callback.from_user.id] = {
        "session_id": session_id,
        "keyboard": keyboard,
        "position": 0,
        "question_id": exam_question.id
    }

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=exam_question.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        # если один из них с фото, другой — без (нельзя изменить)
        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=exam_question.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data.startswith("exam_variant_"))
async def exam_variant_selected(callback: CallbackQuery):
    cache = user_question_cache.get(callback.from_user.id)
    position = cache["position"]

    previous_has_photo = callback.message.photo is not None
    
    sq = await rq.get_session_question(cache["session_id"], position)
    if not sq:
        if not previous_has_photo:
            await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        return
    exam_questions_list = await rq.get_questions('exam')
    exam_question = await rq.get_question(sq.question_id)

    if sq.selected_answer is not None:
        await callback.answer("Siz bu savolga allaqachon javob bergansiz.")
        return

    selected_index = int(callback.data.replace("exam_variant_", ""))
    shuffled_options = sq.shuffled_options
    if selected_index >= len(shuffled_options):
        await rq.end_session(int(cache["session_id"]))
        await callback.answer("Xatolik yuz berdi: noto‘g‘ri variant.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=kb.uz_to_main_menu_kb)
        return
    
    selected_answer = shuffled_options[selected_index]
    await rq.set_selected_answer(sq.id, selected_answer)
    
    await rq.add_answer(
        user_id=callback.from_user.id,
        test_session_id=cache["session_id"],
        question_id=exam_question.id,
        user_answer=selected_answer,
        is_correct=(selected_answer == exam_question.correct_answer)
    )
    
    answer = await rq.get_user_answer(cache["session_id"], exam_question.id)
    
    correct_index: int
    for i, opt in enumerate(sq.shuffled_options):
        if opt == exam_question.correct_answer:
            correct_index = i

    if answer.is_correct:
        await rq.increment_correct_count(cache["session_id"])
        await callback.answer(text="✅ To'g'ri javob berdingiz!")
        await callback.message.edit_reply_markup(reply_markup=kb.mark_answer_variants_kb(sq.shuffled_options, 'exam', answer, position, cache["session_id"], len(exam_questions_list), correct_index))
    elif not answer.is_correct:
        await rq.add_mistake(callback.from_user.id, exam_question.id)
        await rq.increment_incorrect_count(cache["session_id"])
        await rq.decrease_exam_chance(cache["session_id"])
        await callback.answer(text="❌ Noto'g'ri javob berdingiz!")
        await callback.message.edit_reply_markup(reply_markup=kb.mark_answer_variants_kb(sq.shuffled_options, 'exam', answer, position, cache["session_id"], len(exam_questions_list), correct_index))
    else:
        await rq.end_session(int(cache["session_id"]))
        await callback.answer(text="⚠ No'malum xatolik yuz berdi. Iltimos keyinroq qaytadan urinib ko'ring", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=kb.user_question_not_found_kb)


@uz_user_router.callback_query(F.data.startswith("exam_question_"))
async def exam_navigate_question(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id

    # Достаём кэш
    cache = user_question_cache.get(user_id)
    if not cache:
        if not previous_has_photo:
            await callback.message.edit_text("Sessiya topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Sessiya topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        return
    
    previous_has_photo = callback.message.photo is not None
    
    if not await rq.has_chance(user_id, cache["session_id"]):
        if not previous_has_photo:
            await rq.end_session(int(cache["session_id"]))
            await callback.message.edit_text("Siz belgilangan miqdordan ko'p xatolikka yo'l qo'ydingiz. O'zingizni qayta sinab ko'rasizmi?", reply_markup=kb.uz_pass_exam_again_kb)
        else:
            await callback.message.delete()
            await rq.end_session(int(cache["session_id"]))
            await callback.message.answer("Siz belgilangan miqdordan ko'p xatolikka yo'l qo'ydingiz. O'zingizni qayta sinab ko'rasizmi?", reply_markup=kb.uz_pass_exam_again_kb)
        return

    position_str = callback.data.split("_")[-1]
    try:
        position = int(position_str)
    except ValueError:
        if not previous_has_photo:
            await callback.message.edit_text("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        return

    session_id = cache["session_id"]

    cache["position"] = position

    # Получаем текущий вопрос
    sq = await rq.get_session_question(session_id, position=position)
    if not sq:
        if not previous_has_photo:
            await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        return

    exam_question = await rq.get_question(sq.question_id)
    answer = await rq.get_user_answer(session_id, exam_question.id)
    exam_questions_list = await rq.get_questions('exam')

    cache["question_id"] = exam_question.id
    
    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>({position + 1}/20) {exam_question.question_number}-savol</b>\n\n{exam_question.text}\n\n"]
    for i, opt in enumerate(sq.shuffled_options, start=1):
        lines.append(f"F{i}. {opt}")
        if opt == exam_question.correct_answer:
            correct_index = i
        if i < len(sq.shuffled_options):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=sq.shuffled_options,
        mode='exam',
        position=position,
        total_questions=len(exam_questions_list),
        session_id=session_id,
        correct_index=correct_index,
        answer=answer
    )

    new_has_photo = exam_question.photo_id != '-'

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=exam_question.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=exam_question.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data == 'exam_test_results')
async def exam_test_results(callback: CallbackQuery):
    cache = user_question_cache.get(callback.from_user.id)
    previous_has_photo = callback.message.photo is not None
    test_results = await rq.get_test_session(cache["session_id"])
    
    await callback.answer()
    await rq.end_session(int(cache["session_id"]))
    await rq.mark_session_passed(int(cache["session_id"]))

    if previous_has_photo:
        await callback.message.delete()
        await callback.message.answer(
            f"<b>Test natijalari</b>\n\n"
            f"<b>To'g'ri javoblar:</b> {test_results.correct_count}\n"
            f"<b>Noto'g'ri javoblar:</b> {test_results.incorrect_count}\n"
            f"<b>Jami yechilgan savollar:</b> {test_results.correct_count + test_results.incorrect_count}\n\n"
            f"Noto'g'ri yechilgan savollar \"✏ Xatoliklar ustida ishlash\" bo'limiga avtomatik ravishda qo'shilgan. Ushbu bo'limni \"Mening statistikam\" bo'limidan topib xatoliklaringiz ustida ishlashingiz mumkin",
            reply_markup=kb.uz_to_main_menu_kb)
    else:
        await callback.message.edit_text(
            f"<b>Test natijalari</b>\n\n"
            f"<b>To'g'ri javoblar:</b> {test_results.correct_count}\n"
            f"<b>Noto'g'ri javoblar:</b> {test_results.incorrect_count}\n"
            f"<b>Jami yechilgan savollar:</b> {test_results.correct_count + test_results.incorrect_count}\n\n"
            f"Noto'g'ri yechilgan savollar \"✏ Xatoliklar ustida ishlash\" bo'limiga avtomatik ravishda qo'shilgan. Ushbu bo'limni \"Mening statistikam\" bo'limidan topib xatoliklaringiz ustida ishlashingiz mumkin",
            reply_markup=kb.uz_to_main_menu_kb)


# ---------------------------------------------------------------------------------Билеты----------------------------------------------------------------------------------------------------
@uz_user_router.callback_query(F.data.in_({'uz_tickets', 'back_to_tickets'}))
async def uz_btn_tickets(callback: CallbackQuery):
    await callback.answer()
    tickets = await rq.get_all_ticket_nums()
    await callback.message.edit_text("👇 Quyidagi biletlardan birini tanlang", reply_markup=kb.generate_ticket_keyboard(tickets, current_page=0))


@uz_user_router.callback_query(F.data.startswith("tickets_page_"))
async def change_ticket_page(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.split("_")[-1])
    tickets = await rq.get_all_ticket_nums()
    await callback.message.edit_reply_markup(reply_markup=kb.generate_ticket_keyboard(tickets, current_page=page))


@uz_user_router.callback_query(F.data.regexp(r"^ticket_(?!variant_|question_|test_results)\d+$"))
async def ticket_selected(callback: CallbackQuery):
    await callback.answer()

    number_str = callback.data.split("_")[-1]
    try:
        number = int(number_str)
    except ValueError:
        await callback.message.answer("Noto‘g‘ri bilet raqami.")
        return

    ticket = await rq.get_ticket_by_number(number)
    if not ticket:
        await callback.message.answer(f"{number}-bilet topilmadi!", reply_markup=kb.ticket_not_found_kb)
        return

    questions_list = await rq.get_questions('ticket', ticket_id=ticket.id)
    session_id = await rq.start_test_session(callback.from_user.id, 'ticket', questions_list, number)

    sq = await rq.get_session_question(session_id, position=0)
    if not sq:
        await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        return

    question = await rq.get_question(sq.question_id)
    answer = await rq.get_user_answer(session_id, question.id)

    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>{question.question_number}-savol</b>\n\n{question.text}\n\n"]
    for i, opt in enumerate(sq.shuffled_options, start=1):
        lines.append(f"F{i}. {opt}")
        if opt == question.correct_answer:
            correct_index = i
        if i < len(sq.shuffled_options):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=sq.shuffled_options,
        mode='ticket',
        position=0,
        total_questions=len(questions_list),
        session_id=session_id,
        correct_index=correct_index,
        answer=answer
    )

    previous_has_photo = callback.message.photo is not None
    new_has_photo = question.photo_id != '-'

    user_question_cache[callback.from_user.id] = {
        "session_id": session_id,
        "ticket_number": number,
        "keyboard": keyboard,
        "ticket_id": ticket.id,
        "position": 0,
        "question_id": question.id
    }

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=question.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        # если один из них с фото, другой — без (нельзя изменить)
        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=question.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data.startswith("ticket_variant_"))
async def ticket_variant_selected(callback: CallbackQuery):
    cache = user_question_cache.get(callback.from_user.id)
    position = cache["position"]

    previous_has_photo = callback.message.photo is not None
    
    sq = await rq.get_session_question(cache["session_id"], position)
    if not sq:
        if not previous_has_photo:
            await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        return
    questions_list = await rq.get_questions('ticket', ticket_id=cache["ticket_id"])
    question = await rq.get_question(sq.question_id)

    if sq.selected_answer is not None:
        await callback.answer("Siz bu savolga allaqachon javob bergansiz.")
        return

    selected_index = int(callback.data.replace("ticket_variant_", ""))
    shuffled_options = sq.shuffled_options
    if selected_index >= len(shuffled_options):
        await rq.end_session(int(cache["session_id"]))
        await callback.answer("Xatolik yuz berdi: noto‘g‘ri variant.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=kb.user_question_not_found_kb)
        return
    
    selected_answer = shuffled_options[selected_index]
    await rq.set_selected_answer(sq.id, selected_answer)
    
    await rq.add_answer(
        user_id=callback.from_user.id,
        test_session_id=cache["session_id"],
        question_id=question.id,
        user_answer=selected_answer,
        is_correct=(selected_answer == question.correct_answer)
    )
    
    answer = await rq.get_user_answer(cache["session_id"], question.id)

    correct_index: int
    for i, opt in enumerate(sq.shuffled_options):
        if opt == question.correct_answer:
            correct_index = i

    if answer.is_correct:
        await rq.increment_correct_count(cache["session_id"])
        await callback.answer(text="✅ To'g'ri javob berdingiz!")
        await callback.message.edit_reply_markup(reply_markup=kb.mark_answer_variants_kb(sq.shuffled_options, 'ticket', answer, position, cache["session_id"], len(questions_list), correct_index))
    elif not answer.is_correct:
        await rq.add_mistake(callback.from_user.id, question.id)
        await rq.increment_incorrect_count(cache["session_id"])
        await callback.answer(text="❌ Noto'g'ri javob berdingiz!")
        await callback.message.edit_reply_markup(reply_markup=kb.mark_answer_variants_kb(sq.shuffled_options, 'ticket', answer, position, cache["session_id"], len(questions_list), correct_index))
    else:
        await rq.end_session(int(cache["session_id"]))
        await callback.answer(text="⚠ No'malum xatolik yuz berdi. Iltimos keyinroq qaytadan urinib ko'ring", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=kb.user_question_not_found_kb)


@uz_user_router.callback_query(F.data.startswith("ticket_question_"))
async def ticket_navigate_question(callback: CallbackQuery):
    await callback.answer()

    previous_has_photo = callback.message.photo is not None

    position_str = callback.data.split("_")[-1]
    try:
        position = int(position_str)
    except ValueError:
        if not previous_has_photo:
            await callback.message.edit_text("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        return

    user_id = callback.from_user.id

    # Достаём кэш
    cache = user_question_cache.get(user_id)
    if not cache:
        if not previous_has_photo:
            await callback.message.edit_text("Sessiya topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Sessiya topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        return

    session_id = cache["session_id"]

    cache["position"] = position

    # Получаем текущий вопрос
    sq = await rq.get_session_question(session_id, position=position)
    if not sq:
        if not previous_has_photo:
            await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        return

    question = await rq.get_question(sq.question_id)
    answer = await rq.get_user_answer(session_id, question.id)
    questions_list = await rq.get_questions('ticket', ticket_id=cache["ticket_id"])

    cache["question_id"] = question.id
    
    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>{question.question_number}-savol</b>\n\n{question.text}\n\n"]
    for i, opt in enumerate(sq.shuffled_options, start=1):
        lines.append(f"F{i}. {opt}")
        if opt == question.correct_answer:
            correct_index = i
        if i < len(sq.shuffled_options):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=sq.shuffled_options,
        mode='ticket',
        position=position,
        total_questions=len(questions_list),
        session_id=session_id,
        correct_index=correct_index,
        answer=answer
    )

    new_has_photo = question.photo_id != '-'

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=question.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=question.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data == 'save_question')
async def save_answer(callback: CallbackQuery):
    cache = user_question_cache.get(callback.from_user.id)

    has_saved_question = await rq.get_saved_question(callback.from_user.id, cache["question_id"])
    if has_saved_question:
        await callback.answer("❗ Siz bu savolni allaqachon saqlab qo'ygansiz", show_alert=True)
        return
    
    await rq.add_saved_question(callback.from_user.id, cache["question_id"])
    await callback.answer("✔ Savol muvaffaqiyatli saqlandi!", show_alert=True)


@uz_user_router.callback_query(F.data == 'ticket_test_results')
async def ticket_test_results(callback: CallbackQuery):
    cache = user_question_cache.get(callback.from_user.id)
    previous_has_photo = callback.message.photo is not None
    test_results = await rq.get_test_session(cache["session_id"])
    
    await callback.answer()
    await rq.end_session(int(cache["session_id"]))
    await rq.mark_session_passed(int(cache["session_id"]))

    if previous_has_photo:
        await callback.message.delete()
        await callback.message.answer(
            f"<b>Test natijalari</b>\n\n"
            f"<b>To'g'ri javoblar:</b> {test_results.correct_count}\n"
            f"<b>Noto'g'ri javoblar:</b> {test_results.incorrect_count}\n"
            f"<b>Jami yechilgan savollar:</b> {test_results.correct_count + test_results.incorrect_count}\n\n"
            f"Noto'g'ri yechilgan savollar \"✏ Xatoliklar ustida ishlash\" bo'limiga avtomatik ravishda qo'shilgan. Ushbu bo'limni \"Mening statistikam\" bo'limidan topib xatoliklaringiz ustida ishlashingiz mumkin",
            reply_markup=kb.user_question_not_found_kb)
    else:
        await callback.message.edit_text(
            f"<b>Test natijalari</b>\n\n"
            f"<b>To'g'ri javoblar:</b> {test_results.correct_count}\n"
            f"<b>Noto'g'ri javoblar:</b> {test_results.incorrect_count}\n"
            f"<b>Jami yechilgan savollar:</b> {test_results.correct_count + test_results.incorrect_count}\n\n"
            f"Noto'g'ri yechilgan savollar \"✏ Xatoliklar ustida ishlash\" bo'limiga avtomatik ravishda qo'shilgan. Ushbu bo'limni \"Mening statistikam\" bo'limidan topib xatoliklaringiz ustida ishlashingiz mumkin",
            reply_markup=kb.user_question_not_found_kb)


# -----------------------------------------------------------------------------Моя статистика-------------------------------------------------------------------------------------------------
@uz_user_router.callback_query(F.data == 'uz_stats')
async def uz_btn_stats(callback: CallbackQuery):
    await callback.answer()
    user = await rq.get_or_create_user(callback.from_user.id)

    total = user.correct_answers + user.incorrect_answers
    if total == 0:
        await callback.message.edit_text("Siz hali hech qanday savolga javob bermagansiz.", reply_markup=kb.uz_to_main_menu_kb)
        return
    
    correct_percent = round((user.correct_answers / total) * 100, 1)
    incorrect_percent = round((user.incorrect_answers / total) * 100, 1)

    await callback.message.edit_text(
        f"<b>Sizning statistikangiz</b>\n\n"
        f"<b>Umumiy ko'rsatkich:</b>\n"
        f"✅ <b>To'g'ri javoblar:</b> {user.correct_answers} ({correct_percent}%)\n"
        f"❌ <b>Noto'g'ri javoblar:</b> {user.incorrect_answers} ({incorrect_percent}%)\n"
        f"📌 <b>Jami javoblar:</b> {total}",
        reply_markup=kb.uz_stats_kb
    )


@uz_user_router.callback_query(F.data == 'uz_mistakes')
async def uz_fix_mistakes(callback: CallbackQuery):
    await callback.answer()
    mistakes_list = await rq.get_questions(mode='mistakes', user_id=callback.from_user.id)

    if not mistakes_list:
        await callback.message.edit_text(
            "🥳 Sizda noto'g'ri javob berilgan savollar mavjud emas.",
            reply_markup=kb.uz_to_main_menu_kb
        )
        return

    mistake = mistakes_list[0]
    session_id = await rq.start_test_session(callback.from_user.id, 'mistakes', mistakes_list)
    sq = await rq.get_session_question(session_id, position=0)
    if not sq:
        await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        return
    answer = await rq.get_user_answer(session_id, mistake.id)

    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>{mistake.question_number}-savol</b>\n\n{mistake.text}\n\n"]
    for i, opt in enumerate(sq.shuffled_options, start=1):
        lines.append(f"F{i}. {opt}")
        if opt == mistake.correct_answer:
            correct_index = i
        if i < len(sq.shuffled_options):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=sq.shuffled_options,
        mode='mistakes',
        position=0,
        total_questions=len(mistakes_list),
        session_id=session_id,
        correct_index=correct_index,
        answer=answer
    )
    
    previous_has_photo = callback.message.photo is not None
    new_has_photo = mistake.photo_id != '-'

    user_question_cache[callback.from_user.id] = {
        "session_id": session_id,
        "keyboard": keyboard,
        "position": 0,
        "question_id": mistake.id
    }

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=mistake.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        # если один из них с фото, другой — без (нельзя изменить)
        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=mistake.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data.startswith("mistakes_variant_"))
async def mistakes_variant_selected(callback: CallbackQuery):
    cache = user_question_cache.get(callback.from_user.id)
    position = cache["position"]

    previous_has_photo = callback.message.photo is not None
    
    sq = await rq.get_session_question(cache["session_id"], position)
    if not sq:
        if not previous_has_photo:
            await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        return
    mistakes_list = await rq.get_questions(mode='mistakes', user_id=callback.from_user.id)
    mistake = await rq.get_question(sq.question_id)

    if sq.selected_answer is not None:
        await callback.answer("Siz bu savolga allaqachon javob bergansiz.")
        return

    selected_index = int(callback.data.replace("mistakes_variant_", ""))
    shuffled_options = sq.shuffled_options
    if selected_index >= len(shuffled_options):
        await rq.end_session(int(cache["session_id"]))
        await callback.answer("Xatolik yuz berdi: noto‘g‘ri variant.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=kb.uz_to_main_menu_kb)
        return
    
    selected_answer = shuffled_options[selected_index]
    await rq.set_selected_answer(sq.id, selected_answer)
    
    await rq.add_answer(
        user_id=callback.from_user.id,
        test_session_id=cache["session_id"],
        question_id=mistake.id,
        user_answer=selected_answer,
        is_correct=(selected_answer == mistake.correct_answer)
    )
    
    answer = await rq.get_user_answer(cache["session_id"], mistake.id)

    correct_index: int
    for i, opt in enumerate(sq.shuffled_options):
        if opt == mistake.correct_answer:
            correct_index = i

    if answer.is_correct:
        await rq.increment_correct_count(cache["session_id"])
        await rq.mark_mistake_ready_for_delete(callback.from_user.id, mistake.id)
        await callback.answer(text="✅ To'g'ri javob berdingiz!")
        await callback.message.edit_reply_markup(reply_markup=kb.mark_answer_variants_kb(sq.shuffled_options, 'mistakes', answer, position, cache["session_id"], len(mistakes_list), correct_index))
    elif not answer.is_correct:
        await rq.increment_incorrect_count(cache["session_id"])
        await callback.answer(text="❌ Noto'g'ri javob berdingiz!")
        await callback.message.edit_reply_markup(reply_markup=kb.mark_answer_variants_kb(sq.shuffled_options, 'mistakes', answer, position, cache["session_id"], len(mistakes_list), correct_index))
    else:
        await rq.end_session(int(cache["session_id"]), callback.from_user.id)
        await callback.answer(text="⚠ No'malum xatolik yuz berdi. Iltimos keyinroq qaytadan urinib ko'ring", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=kb.user_question_not_found_kb)


@uz_user_router.callback_query(F.data.startswith("mistakes_question_"))
async def mistakes_navigate_question(callback: CallbackQuery):
    await callback.answer()
    
    previous_has_photo = callback.message.photo is not None

    position_str = callback.data.split("_")[-1]
    try:
        position = int(position_str)
    except ValueError:
        if not previous_has_photo:
            await callback.message.edit_text("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        return

    user_id = callback.from_user.id

    # Достаём кэш
    cache = user_question_cache.get(user_id)
    if not cache:
        if not previous_has_photo:
            await callback.message.edit_text("Sessiya topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Sessiya topilmadi.", reply_markup=kb.uz_to_main_menu_kb)
        return

    session_id = cache["session_id"]

    cache["position"] = position

    # Получаем текущий вопрос
    sq = await rq.get_session_question(session_id, position=position)
    if not sq:
        if not previous_has_photo:
            await callback.message.edit_text("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Savol topilmadi.", reply_markup=kb.user_question_not_found_kb)
        return

    mistake = await rq.get_question(sq.question_id)
    answer = await rq.get_user_answer(session_id, mistake.id)
    mistakes_list = await rq.get_questions(mode='mistakes', user_id=user_id)

    cache["question_id"] = mistake.id

    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>{mistake.question_number}-savol</b>\n\n{mistake.text}\n\n"]
    for i, opt in enumerate(sq.shuffled_options, start=1):
        lines.append(f"F{i}. {opt}")
        if opt == mistake.correct_answer:
            correct_index = i
        if i < len(sq.shuffled_options):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=sq.shuffled_options,
        mode='mistakes',
        position=position,
        total_questions=len(mistakes_list),
        session_id=session_id,
        correct_index=correct_index,
        answer=answer
    )

    new_has_photo = mistake.photo_id != '-'

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=mistake.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=mistake.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data == 'mistakes_test_results')
async def mistakes_test_results(callback: CallbackQuery):
    cache = user_question_cache.get(callback.from_user.id)
    previous_has_photo = callback.message.photo is not None
    test_results = await rq.get_test_session(cache["session_id"])
    
    await callback.answer()
    await rq.end_session(int(cache["session_id"]), callback.from_user.id)
    await rq.mark_session_passed(int(cache["session_id"]))

    if previous_has_photo:
        await callback.message.delete()
        await callback.message.answer(
            f"<b>Test natijalari</b>\n\n"
            f"<b>To'g'ri javoblar:</b> {test_results.correct_count}\n"
            f"<b>Noto'g'ri javoblar:</b> {test_results.incorrect_count}\n"
            f"<b>Jami yechilgan savollar:</b> {test_results.correct_count + test_results.incorrect_count}\n\n"
            f"To'g'ri yechilgan savollar \"✏ Xatoliklar ustida ishlash\" bo'limidan avtomatik ravishda o'chiriladi. To'g'ri yechilganlari esa qolishadi.",
            reply_markup=kb.uz_to_main_menu_kb)
    else:
        await callback.message.edit_text(
            f"<b>Test natijalari</b>\n\n"
            f"<b>To'g'ri javoblar:</b> {test_results.correct_count}\n"
            f"<b>Noto'g'ri javoblar:</b> {test_results.incorrect_count}\n"
            f"<b>Jami yechilgan savollar:</b> {test_results.correct_count + test_results.incorrect_count}\n\n"
            f"To'g'ri yechilgan savollar \"✏ Xatoliklar ustida ishlash\" bo'limidan avtomatik ravishda o'chiriladi. To'g'ri yechilganlari esa qolishadi.",
            reply_markup=kb.uz_to_main_menu_kb)


# ---------------------------------------------------------------------------Сохраненные билеты-----------------------------------------------------------------------------------------------
@uz_user_router.callback_query(F.data == 'uz_saved_questions')
async def uz_btn_saved_questions(callback: CallbackQuery):
    await callback.answer()
    questions_list = await rq.get_questions('saved', user_id=callback.from_user.id)
    
    if not questions_list:
        await callback.message.edit_text(
            "Sizda saqlangan savollar mavjud emas.",
            reply_markup=kb.uz_to_main_menu_kb
        )
        return

    question = questions_list[0]

    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>{question.question_number}-savol</b>\n\n{question.text}\n\n"]
    for i, opt in enumerate(question.options):
        lines.append(f"F{i+1}. {opt}")
        if opt == question.correct_answer:
            correct_index = i
        if i < (len(question.options) - 1):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=question.options,
        mode='saved',
        position=0,
        total_questions=len(questions_list),
        correct_index=correct_index
    )
    previous_has_photo = callback.message.photo is not None
    new_has_photo = question.photo_id != '-'

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=question.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        # если один из них с фото, другой — без (нельзя изменить)
        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=question.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data.startswith("saved_question_"))
async def saved_navigate_question(callback: CallbackQuery):
    await callback.answer()

    previous_has_photo = callback.message.photo is not None
    
    position_str = callback.data.split("_")[-1]
    try:
        position = int(position_str)
    except ValueError:
        if not previous_has_photo:
            await callback.message.edit_text("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Noto'g'ri savol raqami.", reply_markup=kb.uz_to_main_menu_kb)
        return

    questions_list = await rq.get_questions('saved', user_id=callback.from_user.id)
    if not questions_list:
        if not previous_has_photo:
            await callback.message.edit_text("Sizda saqlangan savollar mavjud emas.", reply_markup=kb.uz_to_main_menu_kb)
        else:
            await callback.message.delete()
            await callback.message.answer("Sizda saqlangan savollar mavjud emas.", reply_markup=kb.uz_to_main_menu_kb)
        return
    
    if position >= len(questions_list):
        # Если позиция вышла за пределы — идём на последний доступный вопрос
        position = len(questions_list) - 1
        if position < 0:
            await callback.message.edit_text("Sizda saqlangan savollar mavjud emas.", reply_markup=kb.uz_to_main_menu_kb)
            return

    question = questions_list[position]
    
    # Формируем текст вопроса
    correct_index: int
    lines = [f"<b>{question.question_number}-savol</b>\n\n{question.text}\n\n"]
    for i, opt in enumerate(question.options):
        lines.append(f"F{i+1}. {opt}")
        if opt == question.correct_answer:
            correct_index = i
        if i < (len(question.options) - 1):
            lines.append("———————————————")
    lines.append("\n\n@yhq_imtihon_bot")
    
    user_question_cache[callback.from_user.id] = {
        "position": position
    }

    question_text = "\n".join(lines)
    keyboard = kb.build_question_keyboard(
        shuffled_options=question.options,
        mode='saved',
        position=position,
        total_questions=len(questions_list),
        correct_index=correct_index
    )

    new_has_photo = question.photo_id != '-'

    try:
        if not previous_has_photo and not new_has_photo:
            await callback.message.edit_text(question_text, reply_markup=keyboard)
            return

        if previous_has_photo and new_has_photo:
            media = InputMediaPhoto(media=question.photo_id, caption=question_text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
            return

        raise Exception("Невозможно отредактировать: разные типы содержимого")

    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass

        if new_has_photo:
            await callback.message.answer_photo(photo=question.photo_id, caption=question_text, reply_markup=keyboard)
        else:
            await callback.message.answer(question_text, reply_markup=keyboard)


@uz_user_router.callback_query(F.data == 'remove_saved_question')
async def delete_saved_question(callback: CallbackQuery):
    await callback.answer()
    cache = user_question_cache.get(callback.from_user.id)
    questions_list = await rq.get_questions('saved', user_id=callback.from_user.id)

    if not questions_list:
        await callback.message.edit_text("Sizda saqlangan savollar mavjud emas", reply_markup=kb.uz_to_main_menu_kb)
        return

    if not cache:
        await callback.answer("⚠ Xatolik: savol pozitsiyasi aniqlanmadi", show_alert=True)
        return
    
    position = cache.get("position", 0)

    if position >= len(questions_list):
        position = len(questions_list) - 1
    if position < 0:
        position = 0
    current_question = questions_list[position]

    # Удаляем из БД
    deleted = await rq.delete_saved_question(
        user_id=callback.from_user.id,
        question_id=current_question.id
    )

    if deleted:

        updated_list = await rq.get_questions('saved', user_id=callback.from_user.id)

        if not updated_list:
            await callback.message.edit_text("Saqlangan savollar qolmadi.", reply_markup=kb.uz_to_main_menu_kb)
            return

        # position корректируем
        if position >= len(updated_list):
            position = len(updated_list) - 1

        new_question = updated_list[position]

        previous_has_photo = callback.message.photo is not None
        new_has_photo = new_question.photo_id != '-'
        
        # Формируем текст вопроса
        correct_index: int
        lines = [f"<b>{new_question.question_number}-savol</b>\n\n{new_question.text}\n\n"]
        for i, opt in enumerate(new_question.options):
            lines.append(f"F{i+1}. {opt}")
            if opt == new_question.correct_answer:
                correct_index = i
            if i < (len(new_question.options) - 1):
                lines.append("———————————————")
        lines.append("\n\n@yhq_imtihon_bot")

        new_question_text = "\n".join(lines)
        keyboard = kb.build_question_keyboard(
            shuffled_options=new_question.options,
            mode='saved',
            position=position,
            total_questions=len(updated_list),
            correct_index=correct_index
        )

        cache["position"] = position
        user_question_cache[callback.from_user.id] = cache

        try:
            if not previous_has_photo and not new_has_photo:
                await callback.message.edit_text(new_question_text, reply_markup=keyboard)
                return

            if previous_has_photo and new_has_photo:
                media = InputMediaPhoto(media=new_question.photo_id, caption=new_question_text)
                await callback.message.edit_media(media=media, reply_markup=keyboard)
                return

            raise Exception("Невозможно отредактировать: разные типы содержимого")

        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass

            if new_has_photo:
                await callback.message.answer_photo(photo=new_question.photo_id, caption=new_question_text, reply_markup=keyboard)
            else:
                await callback.message.answer(new_question_text, reply_markup=keyboard)
    else:
        await callback.answer("❌ Saqlangan savolni o'chirib bo'lmadi. Iltimos qaytadan urinib ko'ring", show_alert=True)


@uz_user_router.callback_query(F.data == 'noop')
async def noop(callback: CallbackQuery):
    await callback.answer()


# -----------------------------------------------------------------------------Дорожные знаки-------------------------------------------------------------------------------------------------
@uz_user_router.callback_query(F.data == 'uz_road_signs')
async def uz_btn_road_signs(callback: CallbackQuery):
    try:
        await callback.answer()
        await callback.message.edit_text(
            f"<b>Yo'l belgilari</b>\n\n"
            f"Bu bo'limda siz yo'l belgilari bilan tanishib chiqishingiz mumkin",
            reply_markup=kb.uz_road_signs_kb
        )
    except Exception as e:
        await callback.message.delete()
        await callback.message.answer(
            f"<b>Yo'l belgilari</b>\n\n"
            f"Bu bo'limda siz yo'l belgilari bilan tanishib chiqishingiz mumkin",
            reply_markup=kb.uz_road_signs_kb
        )
        print(f"Error in uz_btn_road_signs: {e}")


user_sign_cache = {}  # user_id: {"type": ..., "signs": [...], "index": int}


@uz_user_router.callback_query(F.data.startswith("uz:"))
async def show_first_sign(callback: CallbackQuery):
    sign_type = callback.data.split(":")[-1]
    signs = await rq.get_signs_by_type(sign_type)

    if not signs:
        await callback.answer("Bu turdagi belgilar hozircha mavjud emas.", show_alert=True)
        return

    user_sign_cache[callback.from_user.id] = {
        "type": sign_type,
        "signs": signs,
        "index": 0
    }

    sign = signs[0]
    
    if sign.photo_id is None:
        if sign.description == '-':
            await callback.message.edit_text(f"<b>{sign.name}</b>", reply_markup=kb.sign_nav_kb(0, len(signs)))
        else:
            await callback.message.edit_text(f"<b>{sign.name}</b>\n\n{sign.description}", reply_markup=kb.sign_nav_kb(0, len(signs)))
    else:
        if sign.description == '-':
            await callback.message.delete()
            await callback.answer()
            await callback.message.answer_photo(
                photo=sign.photo_id,
                caption=f"<b>{sign.name}</b>",
                reply_markup=kb.sign_nav_kb(0, len(signs))
            )
        else:
            await callback.message.delete()
            await callback.answer()
            await callback.message.answer_photo(
                photo=sign.photo_id,
                caption=f"<b>{sign.name}</b>\n\n{sign.description}",
                reply_markup=kb.sign_nav_kb(0, len(signs))
            )


@uz_user_router.callback_query(F.data.in_(["prev_sign", "next_sign"]))
async def navigate_signs(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    cache = user_sign_cache.get(user_id)
    if not cache:
        await callback.answer("Sessiya topilmadi. Qaytadan urinib ko'ring.", show_alert=True)
        return

    if callback.data == "prev_sign":
        cache["index"] -= 1
    elif callback.data == "next_sign":
        cache["index"] += 1

    signs = cache["signs"]
    index = cache["index"]
    sign = signs[index]

    if sign.photo_id is None:
        try:
            if sign.description == '-':
                await callback.message.edit_text(f"<b>{sign.name}</b>", reply_markup=kb.sign_nav_kb(index, len(signs)))
            else:
                await callback.message.edit_text(f"<b>{sign.name}</b>\n\n{sign.description}", reply_markup=kb.sign_nav_kb(index, len(signs)))
        except Exception:
            if sign.description == '-':
                await callback.message.delete()
                await callback.message.answer(f"<b>{sign.name}</b>", reply_markup=kb.sign_nav_kb(index, len(signs)))
            else:
                await callback.message.delete()
                await callback.message.answer(f"<b>{sign.name}</b>\n\n{sign.description}", reply_markup=kb.sign_nav_kb(index, len(signs)))
    else:
        try:
            if sign.description == '-':
                media = InputMediaPhoto(media=sign.photo_id, caption=f"<b>{sign.name}</b>")
                await callback.message.edit_media(
                    media=media,
                    reply_markup=kb.sign_nav_kb(index, len(signs))
                )
            else:
                media = InputMediaPhoto(media=sign.photo_id, caption=f"<b>{sign.name}</b>\n\n{sign.description}")
                await callback.message.edit_media(
                    media=media,
                    reply_markup=kb.sign_nav_kb(index, len(signs))
                )
        except Exception:
            if sign.description == '-':
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=sign.photo_id,
                    caption=f"<b>{sign.name}</b>",
                    reply_markup=kb.sign_nav_kb(index, len(signs))
                )
            else:
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=sign.photo_id,
                    caption=f"<b>{sign.name}</b>\n\n{sign.description}",
                    reply_markup=kb.sign_nav_kb(index, len(signs))
                )


@uz_user_router.message(F.text == '/info')
async def show_bot_info(message: Message):
    info_text = await rq.get_info_cmd_text()
    try:
        await message.answer(
            info_text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.uz_to_main_menu_kb
        )
    except Exception:
        await message.answer(
            "<b>404</b>\n\nHmmmm... Biz buni tez orada to'g'rilaymiz 😌",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.uz_to_main_menu_kb
        )