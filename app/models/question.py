# app/models/question.py
"""
Модель вопроса приложения медицинского тестирования
Содержит информацию о вопросах теста (открытые и графические)
"""
from flask_sqlalchemy import SQLAlchemy
from app import db
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey

class Question(db.Model):
    """
    Модель вопроса

    Attributes:
        id (int): Уникальный идентификатор вопроса
        question_text (str): Текст вопроса
        question_type (str): Тип вопроса ('open', 'graphic')
        correct_answer (str): Правильный ответ (для открытых: текст, для графических: ID аннотации)
        image_annotation_id (int): ID связанной аннотации изображения
        creator_id (int): ID создателя вопроса
        topic_id (int): ID темы вопроса
        created_at (datetime): Дата создания вопроса
        test (relationship): Связь с тестом
        image_annotation (relationship): Связь с аннотацией изображения
        creator (relationship): Связь с создателем
        topic (relationship): Связь с темой
    """

    __tablename__ = 'questions'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    question_text = db.Column(Text, nullable=False)
    question_type = db.Column(String(20), default='open')  # 'open', 'graphic'
    correct_answer = db.Column(Text)  # Для открытых вопросов: текст, для графических: ID аннотации (если не используется image_annotation_id)
    image_annotation_id = db.Column(Integer, ForeignKey('image_annotations.id')) # Для графических вопросов
    topic_id = db.Column(Integer, ForeignKey('test_topics.id'))  # ID темы вопроса
    creator_id = db.Column(Integer, ForeignKey('users.id'))  # ID создателя вопроса
    created_at = db.Column(DateTime, default=datetime.utcnow)  # Дата создания вопроса

    creator = db.relationship('User', back_populates='creator_questions', lazy=True, foreign_keys=[creator_id])
    topic = db.relationship('TestTopic', back_populates='questions', lazy=True)
    image_annotation = db.relationship('ImageAnnotation', back_populates='questions', lazy=True)


    def __repr__(self):
        """
        Строковое представление объекта вопроса

        Returns:
            str: Строковое представление вопроса
        """
        return f'<Question {self.question_type}: {self.question_text[:50]}...>'

    @property
    def has_image_annotation(self):
        """
        Проверяет, связан ли вопрос с изображением и аннотацией

        Returns:
            bool: True если вопрос имеет изображение и аннотацию, иначе False
        """
        return self.question_type == 'graphic' and self.image_annotation_id is not None