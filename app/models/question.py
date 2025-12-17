# app/models/question.py
"""
Модель вопроса приложения медицинского тестирования
Содержит информацию о вопросах теста (открытые и графические)
"""
from flask_sqlalchemy import SQLAlchemy
from app import db

class Question(db.Model):
    """
    Модель вопроса

    Attributes:
        id (int): Уникальный идентификатор вопроса
        test_id (int): ID теста, к которому относится вопрос
        question_text (str): Текст вопроса
        question_type (str): Тип вопроса ('open', 'graphic')
        correct_answer (str): Правильный ответ
        test (relationship): Связь с тестом
    """

    __tablename__ = 'questions'

    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='open')  # 'open', 'graphic'
    correct_answer = db.Column(db.Text)  # Для открытых вопросов: текст, для графических: ID аннотации

    def __repr__(self):
        """
        Строковое представление объекта вопроса

        Returns:
            str: Строковое представление вопроса
        """
        return f'<Question {self.question_type}: {self.question_text[:50]}...>'