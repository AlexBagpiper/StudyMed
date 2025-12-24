# app/models/user.py
"""
Модель пользователя приложения медицинского тестирования
Содержит информацию о пользователях системы (администраторы, преподаватели, студенты)
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from app import db
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, Text, ForeignKey
import re
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    """
    Модель пользователя системы

    Attributes:
        id (int): Уникальный идентификатор пользователя
        username (str): Email пользователя (уникальный, используется как логин)
        password_hash (str): Хеш пароля пользователя
        role (str): Роль пользователя ('admin', 'teacher', 'student')
        language (str): Язык интерфейса ('ru', 'en')
        theme (str): Выбранная тема оформления
        first_name (str): Имя пользователя (для студентов/преподавателей)
        last_name (str): Фамилия пользователя (для студентов/преподавателей)
        middle_name (str): Отчество пользователя (для студентов/преподавателей)
        group_number (str): Номер группы (для студентов)
        created_at (datetime): Дата создания пользователя
    """

    __tablename__ = 'users'

    # Основные поля
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(120), unique=True, nullable=False)
    password_hash = db.Column(String(120), nullable=False)
    role = db.Column(String(20), default='student')  # 'admin', 'teacher', 'student'
    language = db.Column(String(5), default='ru')  # Язык интерфейса
    theme = db.Column(String(50), default='default')  # Тема оформления
    first_name = db.Column(String(100))  # Имя (для студентов)
    last_name = db.Column(String(100))   # Фамилия (для студентов)
    middle_name = db.Column(String(100)) # Отчество (для студентов)
    group_number = db.Column(String(50)) # Номер группы (для студентов)
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # Связи с другими моделями
    # указывает на атрибут 'user' в TestResult
    test_results = db.relationship('TestResult', back_populates='user', lazy=True)
    # creator_questions - вопросы, созданные пользователем
    creator_questions = db.relationship('Question', back_populates='creator', lazy=True, foreign_keys='Question.creator_id')


    def __repr__(self):
        """
        Строковое представление объекта пользователя

        Returns:
            str: Строковое представление пользователя
        """
        return f'<User {self.username} ({self.role}>)'

    def has_permission(self, required_permission):
        """
        Проверка наличия у пользователя определенного разрешения

        Args:
            required_permission (str): Требуемое разрешение

        Returns:
            bool: True если пользователь имеет разрешение, иначе False
        """
        if self.role == 'admin':
            return True
        elif self.role == 'teacher':
            return required_permission in ['read_results', 'create_tests']
        elif self.role == 'student':
            return required_permission in ['take_tests']
        return False

    def update_profile(self, **kwargs):
        """
        Метод для обновления профиля пользователя

        Args:
            **kwargs: Поля профиля для обновления
        """
        allowed_fields = {'first_name', 'last_name', 'middle_name', 'group_number', 'language', 'theme'}
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(self, field, value)
        db.session.commit()

    def get_formatted_name(self):
        """
        Возвращает форматированное имя пользователя в формате "Фамилия И.О." или "username".

        Returns:
            str: Форматированное имя
        """
        if self.last_name:
            initials = ""
            if self.first_name:
                initials += f"{self.last_name[0]}." if len(self.last_name) > 0 else ""
            if self.middle_name:
                initials += f"{self.middle_name[0]}." if len(self.middle_name) > 0 else ""
            # Убираем лишние точки и пробелы
            #initials = initials.strip(". ")
            if initials:
                return f"{self.first_name} {initials}"
            else:
                # Если есть фамилия, но нет других частей ФИО
                return self.first_name
        # Если фамилии нет, возвращаем username
        return self.username

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def is_valid_email(username):
        """
        Проверяет корректность формата email

        Args:
            username (str): Email для проверки

        Returns:
            bool: True если формат корректен, иначе False
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, username) is not None