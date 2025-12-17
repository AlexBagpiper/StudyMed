# app/routes/main.py
"""
Основные маршруты приложения медицинского тестирования
Содержит главную страницу и общие маршруты
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models.test import Test
from app.models.user import User
from config import Config
from flask_babel import _, get_locale # Импортируем _ и get_locale
from app import db

# Создание Blueprint для основных маршрутов
bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """
    Главная страница приложения - перенаправление на вход или панель
    """
    # Если пользователь уже авторизован, перенаправляем на соответствующую панель
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.index'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher.index'))
        else:  # student
            return redirect(url_for('student.view_tests'))
    else:
        # Если пользователь не авторизован, перенаправляем на страницу входа
        return redirect(url_for('auth.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """
    Маршрут панели управления - перенаправление в зависимости от роли
    """
    if current_user.role == 'admin':
        return redirect(url_for('admin.index'))
    elif current_user.role == 'teacher':
        return redirect(url_for('teacher.index'))
    else:  # student
        return redirect(url_for('student.view_tests'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Маршрут для просмотра и редактирования профиля пользователя

    GET: Отображает форму профиля с текущими данными
    POST: Обрабатывает данные формы и обновляет профиль
    """
    if request.method == 'POST':
        # Обработка данных формы
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        middle_name = request.form.get('middle_name', '').strip()
        group_number = request.form.get('group_number', '').strip()
        language = request.form.get('language', current_user.language)
        theme = request.form.get('theme', current_user.theme)

        # Валидация и обновление данных
        if language not in Config.LANGUAGES:
            flash(_('Неподдерживаемый язык'))
            return render_template('main/profile.html', user=current_user)

        # Проверка существования темы (если применимо)
        import os
        theme_file = os.path.join(Config.THEMES_PATH, f'{theme}.json')
        if not os.path.exists(theme_file):
            flash(_('Указанная тема не найдена'))
            return render_template('main/profile.html', user=current_user)

        # Обновление данных пользователя
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.middle_name = middle_name
        current_user.group_number = group_number
        current_user.language = language
        current_user.theme = theme

        # Обновление сессии
        session['language'] = language
        session['theme'] = theme

        try:
            db.session.commit()
            flash(_('Профиль успешно обновлен'))
            return redirect(url_for('main.profile'))
        except Exception as e:
            db.session.rollback()
            flash(_('Ошибка при обновлении профиля'))
            print(f"DEBUG: Ошибка обновления профиля: {e}") # Дебаг

    return render_template('main/profile.html', user=current_user)