# app/models/__init__.py
"""
Инициализация моделей данных приложения
Объединение всех моделей в одном месте
"""
from flask_sqlalchemy import SQLAlchemy

# Импорт всех моделей
from .user import User
from .test_topics import TestTopic
from .question import Question
from .annotation import ImageAnnotation, TestResult
from .test_variant import Test, Variant

__all__ = ['User', 'Question', 'ImageAnnotation', 'TestResult', 'TestTopic', 'Test', 'Variant']