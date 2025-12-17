# app/models/test.py
"""
Модель теста приложения медицинского тестирования
Содержит информацию о тестах и их структуре
"""
from flask_sqlalchemy import SQLAlchemy
from app import db
from datetime import datetime

class Test(db.Model):
    """
    Модель теста

    Attributes:
        id (int): Уникальный идентификатор теста
        title (str): Название теста
        description (str): Описание теста
        creator_id (int): ID пользователя-создателя
        created_at (datetime): Дата создания теста
        creator (relationship): Связь с пользователем-создателем
        questions (relationship): Связь с вопросами теста
        results (relationship): Связь с результатами теста
    """

    __tablename__ = 'tests'

    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # ID создателя теста
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Связи с другими моделями
    questions = db.relationship('Question', backref='test', lazy=True)
    results = db.relationship('TestResult', backref='test', lazy=True)

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