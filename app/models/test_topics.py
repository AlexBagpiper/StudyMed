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
    """

    __tablename__ = 'test_topics'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), unique=True, nullable=False)
    description = db.Column(Text)
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # НОВАЯ СВЯЗЬ: questions - вопросы, связанные с темой
    questions = db.relationship('Question', back_populates='topic', lazy=True)

    def __repr__(self):
        """
        Строковое представление объекта темы теста

        Returns:
            str: Строковое представление темы
        """
        return f'<TestTopic {self.name}>'


