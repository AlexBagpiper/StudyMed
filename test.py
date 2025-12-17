#!/usr/bin/env python3
"""
Автономный скрипт для создания файла базы данных SQLite с нужной структурой.

Этот скрипт:
1. Определяет модели SQLAlchemy для таблиц приложения.
2. Создает экземпляр SQLAlchemy Engine.
3. Создает все таблицы, определенные в моделях, в новом файле базы данных.
4. Добавляет администратора с логином 'admin' и паролем 'admin'.
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Имя файла базы данных
DB_FILENAME = 'medical_tests.db'

# Создаем базовый класс для моделей
Base = declarative_base()

# --- Определение моделей ---

class User(Base):
    """
    Модель пользователя системы
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(120), nullable=False)
    role = Column(String(20), default='student')  # 'admin', 'teacher', 'student'
    language = Column(String(5), default='ru')  # Язык интерфейса
    theme = Column(String(50), default='default')  # Тема оформления
    first_name = Column(String(100))  # Имя (для студентов)
    last_name = Column(String(100))   # Фамилия (для студентов)
    middle_name = Column(String(100)) # Отчество (для студентов)
    group_number = Column(String(50)) # Номер группы (для студентов)
    created_at = Column(DateTime, default=func.current_timestamp())

    # Связи с другими моделями
    created_tests = relationship('Test', back_populates='creator', foreign_keys='Test.creator_id')
    test_results = relationship('TestResult', back_populates='user')

    def __repr__(self):
        return f'<User {self.username} ({self.role}>)'


class Test(Base):
    """
    Модель теста
    """
    __tablename__ = 'tests'

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    creator_id = Column(Integer, ForeignKey('users.id'))  # ID создателя теста
    created_at = Column(DateTime, default=func.current_timestamp())

    # Связи с другими моделями
    creator = relationship('User', back_populates='created_tests')
    questions = relationship('Question', back_populates='test')
    results = relationship('TestResult', back_populates='test')


class Question(Base):
    """
    Модель вопроса
    """
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), default='open')  # 'open', 'graphic'
    correct_answer = Column(Text)  # Для открытых вопросов: текст, для графических: ID аннотации

    # Связи с другими моделями
    test = relationship('Test', back_populates='questions')


class ImageAnnotation(Base):
    """
    Модель аннотации изображения
    """
    __tablename__ = 'image_annotations'

    id = Column(Integer, primary_key=True)
    filename = Column(String(200), nullable=False)
    annotation_file = Column(String(200))  # Путь к файлу аннотации (JSON или TXT)
    format_type = Column(String(10), default='coco')  # 'coco' или 'yolo'
    labels = Column(Text)  # JSON строка с метками
    created_at = Column(DateTime, default=func.current_timestamp())


class TestResult(Base):
    """
    Модель результата теста
    """
    __tablename__ = 'test_results'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    score = Column(Float, nullable=False)
    answers_json = Column(Text)  # JSON строка с ответами
    metrics_json = Column(Text)  # JSON строка с метриками
    started_at = Column(DateTime)  # Время начала теста
    completed_at = Column(DateTime, default=func.current_timestamp())  # Время завершения теста
    duration_seconds = Column(Integer)  # Продолжительность в секундах

    # Связи с другими моделями
    user = relationship('User', back_populates='test_results')
    test = relationship('Test', back_populates='results')

# --- Основная логика скрипта ---

def main():
    """
    Основная функция скрипта.
    """
    print(f"Проверка наличия файла базы данных: {DB_FILENAME}")

    if os.path.exists(DB_FILENAME):
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл базы данных '{DB_FILENAME}' уже существует.")
        response = input("Вы хотите перезаписать его? (y/N): ")
        if response.lower() != 'y':
            print("Создание отменено.")
            return
        else:
            print(f"Удаление старого файла базы данных...")
            os.remove(DB_FILENAME)

    print(f"Создание нового файла базы данных: {DB_FILENAME}")
    # Создаем SQLAlchemy engine, указывающий на новый файл
    engine = create_engine(f'sqlite:///{DB_FILENAME}', echo=True) # echo=True для отладки

    print("Создание таблиц...")
    # Создаем все таблицы, определенные в Base
    Base.metadata.create_all(engine)
    print("Таблицы созданы успешно.")

    print("Создание сессии и добавление администратора...")
    # Создаем сессию
    Session = sessionmaker(bind=engine)
    session = Session()

    # Проверяем, существует ли уже пользователь 'admin'
    admin_user = session.query(User).filter_by(username='admin').first()
    if admin_user:
        print("Пользователь 'admin' уже существует. Обновляем данные...")
        admin_user.password_hash = 'admin'  # Обновляем пароль
        admin_user.role = 'admin'           # Обновляем роль
    else:
        print("Создание нового пользователя 'admin'...")
        admin_user = User(
            username='admin',
            password_hash='admin',
            role='admin'
        )
        session.add(admin_user)

    try:
        session.commit()
        print("Пользователь 'admin' успешно добавлен/обновлен.")
    except Exception as e:
        session.rollback()
        print(f"Ошибка при добавлении пользователя: {e}")
    finally:
        session.close()

    print(f"База данных '{DB_FILENAME}' успешно создана и инициализирована.")


if __name__ == "__main__":
    main()