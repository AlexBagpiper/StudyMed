# app/models/__init__.py
"""
Инициализация моделей данных приложения
Объединение всех моделей в одном месте
"""
from flask_sqlalchemy import SQLAlchemy

# Импорт всех моделей
from .user import User
from .test import Test
from .question import Question
from .annotation import ImageAnnotation, TestResult

__all__ = ['User', 'Test', 'Question', 'ImageAnnotation', 'TestResult']