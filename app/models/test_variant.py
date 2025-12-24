# app/models/test_variant.py
"""
Модели теста и варианта приложения медицинского тестирования
Содержит информацию о тестах, их структуре и вариантах прохождения
"""
from app import db
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
import json


class Test(db.Model):
    """
    Модель теста

    Attributes:
        id (int): Уникальный идентификатор теста
        name (str): Название теста (обязательное)
        description (str): Описание теста
        structure (str): JSON-список параметров вопросов: [{'topic_id': int, 'question_type': str}, ...]
        created_at (datetime): Дата создания
        creator_id (int): ID создателя (User)
        creator (relationship): Создатель
        variants (relationship): Варианты этого теста (каскадное удаление)
        # results (relationship): Результаты прохождения (активируем позже)
    """
    __tablename__ = 'tests'

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False)
    description = db.Column(Text)
    # Для SQLite используем Text + сериализацию в JSON
    structure = db.Column(Text, default='[]')  # список: [{"topic_id": ..., "question_type": ...}]
    created_at = db.Column(DateTime, default=datetime.utcnow)
    creator_id = db.Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=False)

    # Связи
    creator = relationship('User', backref='created_tests', foreign_keys=[creator_id])
    variants = relationship('Variant', back_populates='test', cascade='all, delete-orphan', passive_deletes=True)
    # results = relationship('TestResult', back_populates='test', cascade='all, delete-orphan')


class Variant(db.Model):
    """
    Модель варианта теста (набор конкретных вопросов)

    Attributes:
        id (int): Уникальный идентификатор варианта
        test_id (int): ID теста (внешний ключ с ON DELETE CASCADE)
        question_id_list (str): JSON-список ID вопросов, соответствующий структуре теста
        created_at (datetime): Дата создания
        test (relationship): Связь с тестом
    """
    __tablename__ = 'variants'

    id = db.Column(Integer, primary_key=True)
    test_id = db.Column(
        Integer,
        ForeignKey('tests.id', ondelete='CASCADE'),
        nullable=False
    )
    # Список ID вопросов: [12, 45, 89, ...]
    question_id_list = db.Column(Text, default='[]')
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # Связь
    test = relationship('Test', back_populates='variants')