# app/models/annotation.py
"""
Модели аннотации и результатов теста приложения медицинского тестирования
Содержит информацию о размеченных изображениях и результатах тестов
"""
from flask_sqlalchemy import SQLAlchemy
from app import db
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, Text, ForeignKey

class ImageAnnotation(db.Model):
    """
    Модель аннотации изображения

    Attributes:
        id (int): Уникальный идентификатор аннотации
        image_file (str): Имя файла изображения
        annotation_file (str): Имя файла аннотации (JSON или TXT)
        format_type (str): Тип формата ('coco', 'yolo')
        created_at (datetime): Дата создания аннотации
        questions (relationship): Связь с вопросами, использующими эту аннотацию
    """

    __tablename__ = 'image_annotations'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    image_file = db.Column(String(200), nullable=False)
    annotation_file = db.Column(String(200))  # Путь к файлу аннотации (COCO/JSON или YOLO/TXT)
    format_type = db.Column(String(10), default='coco')  # 'coco' или 'yolo'
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # НОВОЕ: Связь с вопросами
    questions = db.relationship('Question', back_populates='image_annotation', lazy=True)

    def __repr__(self):
        """
        Строковое представление объекта аннотации

        Returns:
            str: Строковое представление аннотации
        """
        return f'<ImageAnnotation {self.filename} ({self.format_type}>)'

class TestResult(db.Model):
    """
    Модель результата теста

    Attributes:
        id (int): Уникальный идентификатор результата
        user_id (int): ID пользователя
        score (float): Оценка за тест (0.0 - 1.0)
        answers_json (str): JSON строка содержащая все ответы
        metrics_json (str): JSON строка содержащая метрики оценки
        started_at (datetime): Время начала теста
        completed_at (datetime): Время завершения теста
        duration_seconds (int): Продолжительность теста в секундах
        user (relationship): Связь с пользователем
        test (relationship): Связь с тестом
    """

    __tablename__ = 'test_results'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(Integer, ForeignKey('users.id'), nullable=False)
    score = db.Column(Float, nullable=False)
    answers_json = db.Column(Text)  # JSON строка с ответами
    metrics_json = db.Column(Text)  # JSON строка с метриками
    started_at = db.Column(DateTime)  # Время начала теста
    completed_at = db.Column(DateTime, default=datetime.utcnow)  # Время завершения теста
    duration_seconds = db.Column(Integer)  # Продолжительность в секундах

    # Связи с другими моделями
    # ИСПРАВЛЕНО: back_populates='test_results' - указывает на атрибут 'test_results' в User
    user = db.relationship('User', back_populates='test_results')
    # ИСПРАВЛЕНО: back_populates='results' - указывает на атрибут 'results' в Test
    #test = db.relationship('Test', back_populates='results')

    def __repr__(self):
        """
        Строковое представление объекта результата теста

        Returns:
            str: Строковое представление результата теста
        """
        return f'<TestResult user_id={self.user_id}, test_id={self.test_id}, score={self.score}>'