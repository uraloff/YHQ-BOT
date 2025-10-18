import os
import ssl
import enum
from datetime import datetime
from dotenv import load_dotenv

from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy import DateTime, String, BigInteger, ForeignKey, Integer, Enum, Boolean, Text

ENVIRONMENT = os.getenv('BOT_MODE', 'dev')
dotenv_path = os.path.join(os.path.dirname(__file__), f'.env.{ENVIRONMENT}')

load_dotenv(dotenv_path)

db_url = os.getenv("DB_URL")
if not db_url:
    raise RuntimeError("DB_URL not found in environment variables")

if ENVIRONMENT == 'prod':
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    engine = create_async_engine(db_url, connect_args={"ssl": ssl_context})
    async_session = async_sessionmaker(engine)
else:
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass


# -----------------------------------------------------------------------------------Пользователь------------------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now().replace(microsecond=0))
    correct_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    incorrect_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"


# -----------------------------------------------------------------------------------Вопрос--------------------------------------------------------------------------------------------
class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String, nullable=False)
    photo_id: Mapped[str] = mapped_column(String, nullable=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=True)

    def __repr__(self):
        return f"<Question(id={self.id}, question_number={self.question_number}, text={self.text}, options={self.options}, correct_answer={self.correct_answer}, photo_id={self.photo_id} ticket_id={self.ticket_id})>"


# ------------------------------------------------------------------------------------Билет--------------------------------------------------------------------------------------------
class Ticket(Base):
    __tablename__ = 'tickets'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(unique=True, nullable=False)

    def __repr__(self):
        return f"<Ticket(id={self.id}, number={self.number})>"


# -----------------------------------------------------------------------Вопросы с вариантами в каждой сессии---------------------------------------------------------------------------
class SessionQuestion(Base):
    __tablename__ = "session_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    shuffled_options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    selected_answer: Mapped[str | None] = mapped_column(nullable=True)

    def __repr__(self):
        return f"<SessionQuestion(id={self.id}, position={self.position})>"


# ------------------------------------------------------------------------------Сессия прохождения--------------------------------------------------------------------------------------
class TestSession(Base):
    __tablename__ = 'test_sessions'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    ticket_number: Mapped[int] = mapped_column(ForeignKey("tickets.number"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now().replace(microsecond=0))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=True)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # 'exam' | 'ticket' | 'mistakes' | 'saved'
    correct_count: Mapped[int] = mapped_column(default=0)
    incorrect_count: Mapped[int] = mapped_column(default=0)
    passed: Mapped[bool] = mapped_column(default=False)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<TestSession(id={self.id}, user_id={self.user_id}, mode='{self.mode}')>"


# -------------------------------------------------------------------Ответ на конкретный вопрос в сессии-------------------------------------------------------------------------------
class Answer(Base):
    __tablename__ = 'answers'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    test_session_id: Mapped[int] = mapped_column(ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    user_answer: Mapped[str] = mapped_column(nullable=False)
    is_correct: Mapped[bool] = mapped_column(nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now().replace(microsecond=0))

    def __repr__(self):
        return (
            f"<Answer(session_id={self.test_session_id}, question_id={self.question_id}, "
            f"user_answer={self.user_answer}, correct={self.is_correct}, "
            f"user_id={self.user_id}>"
        )


# -----------------------------------------------------------------------------Ошибки пользователя-------------------------------------------------------------------------------------
class Mistake(Base):
    __tablename__ = "mistakes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    ready_for_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return (
            f"<Mistake(user_id={self.user_id}, question_id={self.question_id}, "
            f"ready_for_delete={self.ready_for_delete})>"
        )
    

# -----------------------------------------------------------------------------Сохранённые вопросы-------------------------------------------------------------------------------------
class SavedQuestion(Base):
    __tablename__ = "saved_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now().replace(microsecond=0))

    def __repr__(self):
        return f"<SavedQuestion(user_id={self.user_id}, question_id={self.question_id})>"


# --------------------------------------------------------------------------------Дорожные знаки---------------------------------------------------------------------------------------
class RoadSign(Base):
    __tablename__ = "road_signs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    photo_id: Mapped[str] = mapped_column(String(255), nullable=True)

    def __repr__(self):
        return f"<RoadSign(name='{self.name}', type='{self.type}')>"


# -------------------------------------------------------------------------------------Админы------------------------------------------------------------------------------------------
class AdminStatus(enum.Enum):
    pending = "pending"
    confirmed = "confirmed"

class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now().replace(microsecond=0))
    status: Mapped[AdminStatus] = mapped_column(Enum(AdminStatus), default=AdminStatus.pending, nullable=False)

    def __repr__(self):
        return (
            f"<Admin(telegram_id={self.telegram_id}, "
            f"status={self.status.name}, created_at={self.created_at.isoformat()})>"
        )

# ----------------------------------------------------------------------------------Команды info------------------------------------------------------------------------------------------
class BotInfo(Base):
    __tablename__ = "bot_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)