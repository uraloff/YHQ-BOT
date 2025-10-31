import random

from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func, update, delete

from App.Database.models import async_session, User, Question, Ticket, SessionQuestion, TestSession, Answer, Mistake, SavedQuestion, RoadSign, Admin, AdminStatus, BotInfo


async def get_or_create_user(
    telegram_id: int,
    full_name: str | None = None,
    username: str | None = None,
    referral_code: str | None = None
) -> User:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )
        if user:
            return user

        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            referral_code=referral_code
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            user = await session.scalar(
                select(User).where(User.telegram_id == telegram_id)
            )
        else:
            await session.refresh(user)

        return user


async def get_all_users():
    async with async_session() as session:
        result = await session.scalars(
            select(User.telegram_id)
        )
        return result.all()
    

async def get_users_last_week():
    now = datetime.now()
    start_of_week = (now - timedelta(days=now.weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    async with async_session() as session:
        result = await session.scalars(
            select(User.id)
            .where(User.joined_at >= start_of_week)
            .where(User.joined_at <= end_of_week)
        )
        users = result.all()
        return len(users)


async def get_referral_stats():
    async with async_session() as session:
        result = await session.execute(
            select(User.referral_code, func.count(User.id))
            .where(User.referral_code.isnot(None))
            .group_by(User.referral_code)
        )
        return result.all()


async def get_referral_percentage(referral_code: str) -> int:
    async with async_session() as session:
        total_users_result = await session.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0

        if total_users == 0:
            return 0

        referral_users_result = await session.execute(
            select(func.count(User.id)).where(User.referral_code == referral_code)
        )
        referral_users = referral_users_result.scalar() or 0

        percent = round((referral_users / total_users) * 100)
        return percent


async def handle_admin(telegram_id: int, full_name: str | None = None, username: str | None = None, for_confirm: bool = False, for_cancel: bool = False) -> Admin | None:
    async with async_session() as session:
        admin = await session.scalar(
            select(Admin).where(Admin.telegram_id == telegram_id)
        )

        # === Отклонение (удаление) ===
        if for_cancel:
            if admin:
                await session.delete(admin)
                await session.commit()
            return None

        # === Подтверждение ===
        if for_confirm:
            if admin:
                admin.status = AdminStatus.confirmed
                await session.commit()
                await session.refresh(admin)
            return admin

        # === Создание нового ===
        if not admin:
            admin = Admin(
                telegram_id=telegram_id,
                full_name=full_name,
                username=username,
                status=AdminStatus.pending
            )
            session.add(admin)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                admin = await session.scalar(
                    select(Admin).where(Admin.telegram_id == telegram_id)
                )
            else:
                await session.refresh(admin)

        return admin
    

async def check_confirmed_admin(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.scalar(
            select(Admin).where(
                Admin.telegram_id == telegram_id,
                Admin.status == AdminStatus.confirmed
            )
        )
        return result is not None


async def get_all_ticket_nums():
    async with async_session() as session:
        result = await session.scalars(
            select(Ticket.number).order_by(Ticket.number)
        )
        return result.all()


async def add_road_sign(sign_type: str, sign_name: str, sign_description: str | None = None, sign_photo: str | None = None) -> RoadSign:
    """
    Добавляет дорожный знак в БД.

    :param sign_type: Тип знака
    :param sign_name: Название знака
    :param sign_description: Описание знака (опционально)
    :param sign_photo: file_id от Telegram (опционально)
    :return: Добавленный экземпляр RoadSign
    """
    async with async_session() as session:
        road_sign = RoadSign(
            type=sign_type.strip(),
            name=sign_name.strip(),
            description=sign_description.strip() if sign_description else '-',
            photo_id=sign_photo
        )
        session.add(road_sign)
        try:
            await session.commit()
            await session.refresh(road_sign)
            return road_sign
        except IntegrityError:
            await session.rollback()
            raise ValueError("❌ Такой дорожный знак уже есть или данные некорректны.")


async def get_signs_by_type(sign_type: str):
    async with async_session() as session:
        result = await session.scalars(
            select(RoadSign)
            .where(RoadSign.type == sign_type)
            .order_by(RoadSign.id)
        )
        return result.all()
    

async def get_ticket_by_number(ticket_number: int) -> Ticket | None:
    async with async_session() as session:
        result = await session.scalar(
            select(Ticket).where(Ticket.number == ticket_number)
        )
        return result


async def get_questions(mode: str, **kwargs) -> list[Question]:
    async with async_session() as session:
        questions = []

        match mode:
            case "ticket":
                ticket_id = kwargs.get("ticket_id")
                if ticket_id is None:
                    raise ValueError("ticket_id is required for ticket mode")
                stmt = select(Question).where(Question.ticket_id == ticket_id).order_by(Question.question_number)
                questions = list(await session.scalars(stmt))

            case "exam":
                result = await session.execute(
                    select(Ticket.number)
                    .join(Question, Question.ticket_id == Ticket.id)
                    .group_by(Ticket.id, Ticket.number)
                    .having(func.count(Question.id) == 10)
                )
                valid_ticket_numbers = [row[0] for row in result.all()]
                if len(valid_ticket_numbers) < 2:
                    raise ValueError("Недостаточно билетов с ровно 10 вопросами для режима 'exam'")

                selected_tickets = random.sample(valid_ticket_numbers, 2)
                stmt = (
                    select(Question)
                    .join(Ticket, Question.ticket_id == Ticket.id)
                    .where(Ticket.number.in_(selected_tickets))
                )
                questions = list(await session.scalars(stmt))
                random.shuffle(questions)

            case "mistakes":
                user_id = kwargs.get("user_id")
                if user_id is None:
                    raise ValueError("user_id is required for mistakes mode")
                stmt = (
                    select(Question)
                    .join(Mistake, Mistake.question_id == Question.id)
                    .where(Mistake.user_id == user_id)
                    .order_by(Question.ticket_id, Question.question_number)
                )
                questions = list(await session.scalars(stmt))

            case "saved":
                user_id = kwargs.get("user_id")
                if user_id is None:
                    raise ValueError("user_id is required for saved mode")
                stmt = (
                    select(Question)
                    .join(SavedQuestion, SavedQuestion.question_id == Question.id)
                    .where(SavedQuestion.user_id == user_id)
                    .order_by(Question.ticket_id, Question.question_number)
                )
                questions = list(await session.scalars(stmt))

            case _:
                raise ValueError(f"Unknown mode: {mode}")

        # Прогружаем options, чтобы не было lazy-loading в хендлерах
        _ = [q.options for q in questions]

        return questions


async def start_test_session(user_id: int, mode: str, questions: list, ticket_number: int | None = None) -> int:
    """
    Запускает тестовую сессию для любого режима: ticket, exam, mistakes.

    :param user_id: ID пользователя
    :param mode: режим теста ('ticket', 'exam', 'mistakes')
    :param questions: список вопросов (каждый вопрос должен иметь id и options)
    :param ticket_number: номер билета (только для режима 'ticket')
    :return: ID созданной сессии
    """
    async with async_session() as session:
        new_session = TestSession(
            user_id=user_id,
            mode=mode,
            ticket_number=ticket_number,
            mistake_count=3 if mode == "exam" else 0
        )
        session.add(new_session)
        await session.flush()  # получаем ID сессии до коммита

        session_id = new_session.id

        for index, question in enumerate(questions):
            shuffled = question.options.copy()
            random.shuffle(shuffled)

            session.add(SessionQuestion(
                test_session_id=session_id,
                question_id=question.id,
                position=index,
                shuffled_options=shuffled
            ))

        await session.commit()
        return session_id


async def count_questions_in_ticket(ticket_id: int) -> int:
    async with async_session() as session:
        result = await session.scalar(
            select(func.count()).select_from(Question).where(Question.ticket_id == ticket_id)
        )
        return result


async def get_next_question_number() -> int:
    async with async_session() as session:
        result = await session.execute(select(func.max(Question.question_number)))
        max_number = result.scalar()
        return (max_number or 0) + 1


async def add_question(ticket_id: int, text: str, options: list[str], correct_answer: str, photo_id: str | None = None) -> None:
    async with async_session() as session:
        number = await get_next_question_number()
        question = Question(
            question_number=number,
            ticket_id=ticket_id,
            text=text,
            options=options,
            correct_answer=correct_answer,
            photo_id=photo_id
        )
        session.add(question)
        await session.commit()


async def add_ticket(ticket_num: int) -> None:
    async with async_session() as session:
        ticket = Ticket(number=ticket_num)
        session.add(ticket)
        await session.commit()


async def get_session_question(test_session_id: int, position: int):
    async with async_session() as session:
        return await session.scalar(
            select(SessionQuestion).where(
                SessionQuestion.test_session_id == test_session_id,
                SessionQuestion.position == position
            )
        )


async def get_question(question_id: int):
    async with async_session() as session:
        return await session.scalar(
            select(Question).where(Question.id == question_id)
        )
    

async def add_answer(user_id: int, test_session_id: int, question_id: int, user_answer: str, is_correct: bool = False) -> None:
    async with async_session() as session:
        answer = Answer(
            user_id=user_id,
            test_session_id=test_session_id,
            question_id=question_id,
            user_answer=user_answer,
            is_correct=is_correct
        )

        user = await session.scalar(select(User).where(User.telegram_id == user_id))

        if is_correct:
            user.correct_answers += 1
        else:
            user.incorrect_answers += 1
        session.add(answer)
        await session.commit()


async def get_user_answer(test_session_id: int, question_id: int):
    async with async_session() as session:
        return await session.scalar(
            select(Answer).where(
                Answer.test_session_id == test_session_id,
                Answer.question_id == question_id
            )
        )


async def end_session(session_id: int, user_id: int | None = None):
    async with async_session() as session:
        # Получаем режим сессии
        result = await session.execute(
            select(TestSession.mode, TestSession.user_id)
            .where(TestSession.id == int(session_id))
        )
        row = result.first()

        if not row:
            return  # Нет такой сессии

        mode, session_user_id = row

        # Завершаем сессию
        await session.execute(
            update(TestSession)
            .where(TestSession.id == int(session_id))
            .values(ended_at=datetime.now().replace(microsecond=0))
        )

        # Если передан user_id и режим mistakes → удаляем готовые к удалению ошибки
        if user_id is not None and mode == "mistakes":
            await session.execute(
                delete(Mistake)
                .where(
                    Mistake.user_id == user_id,
                    Mistake.ready_for_delete == True  # noqa: E712
                )
            )

        await session.commit()


async def increment_correct_count(session_id: int):
    async with async_session() as session:
        stmt = (
            update(TestSession)
            .where(TestSession.id == int(session_id))
            .values(correct_count=TestSession.correct_count + 1)
        )
        await session.execute(stmt)
        await session.commit()


async def increment_incorrect_count(session_id: int):
    async with async_session() as session:
        stmt = (
            update(TestSession)
            .where(TestSession.id == int(session_id))
            .values(incorrect_count=TestSession.incorrect_count + 1)
        )
        await session.execute(stmt)
        await session.commit()


async def mark_session_passed(session_id: int):
    async with async_session() as session:
        stmt = (
            update(TestSession)
            .where(TestSession.id == session_id)
            .values(
                passed=True
            )
        )
        await session.execute(stmt)
        await session.commit()


async def set_selected_answer(session_question_id: int, selected_answer: str):
    async with async_session() as session:
        stmt = (
            update(SessionQuestion)
            .where(SessionQuestion.id == session_question_id)
            .values(selected_answer=selected_answer)
        )
        await session.execute(stmt)
        await session.commit()

    
async def add_mistake(user_id: int, question_id: int) -> None:
    async with async_session() as session:
        existing = await session.scalar(
            select(Mistake).where(
                Mistake.user_id == user_id,
                Mistake.question_id == question_id
            )
        )
        if existing:
            return

        mistake = Mistake(
            user_id=user_id,
            question_id=question_id
        )
        session.add(mistake)
        await session.commit()

    
async def add_saved_question(user_id: int, question_id: int) -> None:
    async with async_session() as session:
        saved_question = SavedQuestion(
            user_id=user_id,
            question_id=question_id
        )
        session.add(saved_question)
        await session.commit()


async def get_saved_question(user_id: int, question_id: int | None = None) -> SavedQuestion | None:
    async with async_session() as session:
        stmt = select(SavedQuestion).where(SavedQuestion.user_id == user_id)
        if question_id is not None:
            stmt = stmt.where(SavedQuestion.question_id == question_id)
        return await session.scalar(stmt)


async def get_test_session(session_id: int):
    async with async_session() as session:
        return await session.scalar(
            select(TestSession).where(TestSession.id  == session_id)
        )
    

async def delete_saved_question(user_id: int, question_id: int) -> bool:
    """
    Удаляет сохранённый вопрос для пользователя.
    Возвращает True, если удаление прошло успешно (хотя бы 1 запись удалена), иначе False.
    """
    async with async_session() as session:
        stmt = delete(SavedQuestion).where(
            SavedQuestion.user_id == user_id,
            SavedQuestion.question_id == question_id
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
    

async def mark_mistake_ready_for_delete(user_id: int, question_id: int) -> None:
    async with async_session() as session:
        await session.execute(
            update(Mistake)
            .where(Mistake.user_id == user_id, Mistake.question_id == question_id)
            .values(ready_for_delete=True)
        )
        await session.commit()


async def has_chance(user_id: int, session_id: int) -> bool:
    """
    Проверяет, остались ли у пользователя шансы в тестовой сессии.
    Логика: шанс есть, если mistake_count < MAX_MISTAKES.
    """
    async with async_session() as session:
        result = await session.execute(
            select(TestSession.mistake_count)
            .where(TestSession.user_id == user_id, TestSession.id == session_id)
        )
        mistake_count = result.scalar_one_or_none()

        if mistake_count is None:
            raise ValueError(f"Сессия {session_id} для пользователя {user_id} не найдена")

        return mistake_count > 0 and mistake_count <= 3
    

async def decrease_exam_chance(session_id: int) -> None:
    """
    Уменьшает количество оставшихся шансов в экзаменационной сессии на 1.

    :param session_id: ID тестовой сессии
    """
    async with async_session() as session:
        stmt = (
            select(TestSession)
            .where(
                TestSession.id == session_id,
                TestSession.mode == "exam",
                TestSession.ended_at.is_(None)
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        test_session = result.scalar_one_or_none()

        if test_session and test_session.mistake_count > 0:
            test_session.mistake_count -= 1
            await session.commit()


async def change_info_cmd_text(text: str) -> None:
    async with async_session() as session:
        result = await session.execute(select(BotInfo))
        bot_info = result.scalar_one_or_none()

        if bot_info:
            bot_info.text = text
        else:
            session.add(BotInfo(text=text))

        await session.commit()


async def get_info_cmd_text() -> str:
    async with async_session() as session:
        result = await session.execute(select(BotInfo.text))
        bot_info_text = result.scalar_one_or_none()

        if not bot_info_text:
            raise ValueError("Информация о боте не найдена в базе данных")

        return bot_info_text