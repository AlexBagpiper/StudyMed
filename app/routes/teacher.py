# app/routes/teacher.py
"""
Маршруты преподавателя приложения медицинского тестирования
Содержит логику для преподавателей
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.test import Test
from app.models.annotation import TestResult

# Создание Blueprint для маршрутов преподавателя
bp = Blueprint('teacher', __name__)

@bp.route('/teacher')
@login_required
def index():
    """
    Главная страница преподавателя

    Проверяет права доступа и отображает панель управления
    """
    if current_user.role not in ['admin', 'teacher']:
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

    # Преподаватель видит только свои тесты
    if current_user.role == 'teacher':
        tests = Test.query.filter_by(creator_id=current_user.id).all()
        # Получение результатов для тестов преподавателя
        teacher_tests = Test.query.filter_by(creator_id=current_user.id).with_entities(Test.id).all()
        test_ids = [test.id for test in teacher_tests]
        results = TestResult.query.filter(TestResult.test_id.in_(test_ids)).all()
    else:  # admin
        tests = Test.query.all()
        results = TestResult.query.all()

    return render_template('teacher/index.html', tests=tests, results=results)