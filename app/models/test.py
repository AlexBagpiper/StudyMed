# app/models/test.py
"""
Модель теста приложения медицинского тестирования
Содержит информацию о тестах и их структуре
"""
from flask_sqlalchemy import SQLAlchemy
from app import db
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey

class TestTopic(db.Model):
    """
    Модель темы теста

    Attributes:
        id (int): Уникальный идентификатор темы
        name (str): Название темы (уникальное)
        description (str): Описание темы
        created_at (datetime): Дата создания темы
        tests (relationship): Связь с тестами по этой теме
    """

    __tablename__ = 'test_topics'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), unique=True, nullable=False)
    description = db.Column(Text)
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # Связи с другими моделями
    tests = db.relationship('Test', back_populates='topic', lazy=True)
    # НОВАЯ СВЯЗЬ: questions - вопросы, связанные с темой
    questions = db.relationship('Question', back_populates='topic', lazy=True)

    def __repr__(self):
        """
        Строковое представление объекта темы теста

        Returns:
            str: Строковое представление темы
        """
        return f'<TestTopic {self.name}>'


class Test(db.Model):
    """
    Модель теста

    Attributes:
        id (int): Уникальный идентификатор теста
        title (str): Название теста
        description (str): Описание теста
        topic_id (int): ID темы теста
        creator_id (int): ID создателя теста
        created_at (datetime): Дата создания теста
        topic (relationship): Связь с темой
        creator (relationship): Связь с создателем
    """

    __tablename__ = 'tests'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    title = db.Column(String(200), nullable=False)
    description = db.Column(Text)
    topic_id = db.Column(Integer, ForeignKey('test_topics.id'))  # ID темы
    creator_id = db.Column(Integer, ForeignKey('users.id'))  # ID создателя теста
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # Связи с другими моделями
    # ИСПРАВЛЕНО: back_populates='tests' - указывает на атрибут 'tests' в TestTopic
    topic = db.relationship('TestTopic', back_populates='tests', lazy=True)
    # ИСПРАВЛЕНО: back_populates='created_tests' - указывает на атрибут 'created_tests' в User
    #creator = db.relationship('User', back_populates='created_tests', lazy=True, foreign_keys=[creator_id])

    def __repr__(self):
        """
        Строковое представление объекта теста

        Returns:
            str: Строковое представление теста
        """
        return f'<Test {self.title}>'

    @property
    def question_count(self):
        """
        Количество вопросов в тесте

        Returns:
            int: Количество вопросов
        """
        return len(self.questions)