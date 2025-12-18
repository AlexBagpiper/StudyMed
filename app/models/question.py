# app/models/question.py
"""
Модель вопроса приложения медицинского тестирования
Содержит информацию о вопросах теста (открытые и графические)
"""
from flask_sqlalchemy import SQLAlchemy
from app import db
from sqlalchemy import String, Integer, Text, ForeignKey

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
    id = db.Column(Integer, primary_key=True)
    test_id = db.Column(Integer, ForeignKey('tests.id'), nullable=False)
    question_text = db.Column(Text, nullable=False)
    question_type = db.Column(String(20), default='open')  # 'open', 'graphic'
    # Для открытых вопросов: текст, для графических: ID аннотации
    correct_answer = db.Column(Text)

    # Связи с другими моделями
    # ИСПРАВЛЕНО: back_populates='questions' - указывает на атрибут 'questions' в Test
    test = db.relationship('Test', back_populates='questions', lazy=True)

    def __repr__(self):
        """
        Строковое представление объекта вопроса

        Returns:
            str: Строковое представление вопроса
        """
        return f'<Question {self.question_type}: {self.question_text[:50]}...>'