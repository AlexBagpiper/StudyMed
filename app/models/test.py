# app/models/test.py
"""
Модель теста приложения медицинского тестирования
Содержит информацию о тестах и их структуре
"""
from flask_sqlalchemy import SQLAlchemy
from app import db
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey

class Test(db.Model):
    """
    Модель теста

    Attributes:
        id (int): Уникальный идентификатор теста
        title (str): Название теста
        description (str): Описание теста
        creator_id (int): ID создателя теста
        created_at (datetime): Дата создания теста
        creator (relationship): Связь с создателем
        questions (relationship): Связь с вопросами
        results (relationship): Связь с результатами
    """

    __tablename__ = 'tests'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    title = db.Column(String(200), nullable=False)
    description = db.Column(Text)
    creator_id = db.Column(Integer, ForeignKey('users.id'))  # ID создателя теста
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # Связи с другими моделями
    # ИСПРАВЛЕНО: back_populates='created_tests' - указывает на атрибут 'created_tests' в User
    creator = db.relationship('User', back_populates='created_tests', foreign_keys=[creator_id])
    # ИСПРАВЛЕНО: back_populates='test' - указывает на атрибут 'test' в Question
    questions = db.relationship('Question', back_populates='test', lazy=True)
    # ИСПРАВЛЕНО: back_populates='test' - указывает на атрибут 'test' в TestResult
    results = db.relationship('TestResult', back_populates='test', lazy=True)

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