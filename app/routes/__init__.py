# app/routes/__init__.py
"""
Инициализация маршрутов приложения
Объединение всех модулей маршрутов в одном месте
"""
from flask import Blueprint

# Определение всех blueprints
__all__ = ['auth_bp', 'main_bp', 'admin_bp', 'teacher_bp', 'student_bp', 'database_bp']