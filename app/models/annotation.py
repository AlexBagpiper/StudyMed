# app/models/annotation.py
"""
Модель аннотации и результатов теста приложения медицинского тестирования
Содержит информацию о размеченных изображениях и результатах тестирования
"""
from flask_sqlalchemy import SQLAlchemy
from app import db
from datetime import datetime

class ImageAnnotation(db.Model):
    """
    Модель аннотации изображения

    Attributes:
        id (int): Уникальный идентификатор аннотации
        filename (str): Имя файла изображения
        annotation_file (str): Имя файла аннотации
        format_type (str): Тип формата ('coco', 'yolo')
        labels (str): JSON строка с метками
        created_at (datetime): Дата создания аннотации
    """

    __tablename__ = 'image_annotations'

    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    annotation_file = db.Column(db.String(200))  # Путь к файлу аннотации (JSON или TXT)
    format_type = db.Column(db.String(10), default='coco')  # 'coco' или 'yolo'
    labels = db.Column(db.Text)  # JSON строка с метками
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
        test_id (int): ID теста
        score (float): Оценка за тест (0.0 - 1.0)
        answers_json (str): JSON строка с ответами
        metrics_json (str): JSON строка с метриками
        started_at (datetime): Время начала теста
        completed_at (datetime): Время завершения теста
        duration_seconds (int): Продолжительность теста в секундах
        user (relationship): Связь с пользователем
        test (relationship): Связь с тестом
    """

    __tablename__ = 'test_results'

    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    answers_json = db.Column(db.Text)  # JSON строка с ответами
    metrics_json = db.Column(db.Text)  # JSON строка с метриками
    started_at = db.Column(db.DateTime)  # Время начала теста
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)  # Время завершения теста
    duration_seconds = db.Column(db.Integer)  # Продолжительность в секундах

    def __repr__(self):
        """
        Строковое представление объекта результата теста

        Returns:
            str: Строковое представление результата теста
        """
        return f'<TestResult user_id={self.user_id}, test_id={self.test_id}, score={self.score}>'