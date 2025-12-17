# app/routes/auth.py
"""
Маршруты аутентификации приложения медицинского тестирования
Содержит логику входа, регистрации и выхода пользователей
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from config import Config
from flask_babel import _ # Импортируем _ для перевода flash-сообщений
from urllib.parse import urlparse, urljoin # Импортируем urlparse и urljoin

# Создание Blueprint для маршрутов аутентификации
# Убедимся, что имя переменной 'bp'
bp = Blueprint('auth', __name__) # Имя Blueprint 'auth'

@bp.route('/login', methods=['GET', 'POST']) # Маршрут для /login относительно префикса Blueprint
def login():
    """
    Маршрут для входа в систему

    GET: Отображает форму входа
    POST: Обрабатывает данные формы входа
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Поиск пользователя в базе данных
        user = User.query.filter_by(username=username).first()

        # Проверка пароля и аутентификация
        # ВНИМАНИЕ: В реальном приложении используйте хеширование паролей!
        if user and user.password_hash == password:
            login_user(user)

            # Сохранение языка и темы в сессии
            session['language'] = user.language
            session['theme'] = user.theme

            # Перенаправление в зависимости от роли пользователя
            if user.role == 'admin':
                return redirect(url_for('admin.index'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher.index'))
            else:  # student
                return redirect(url_for('student.view_tests'))
        else:
            flash(_('Неверные учетные данные'))

    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST']) # Маршрут для /register относительно префикса Blueprint
def register():
    """
    Маршрут для регистрации нового пользователя

    GET: Отображает форму регистрации
    POST: Обрабатывает данные формы регистрации
    """
    if request.method == 'POST':
        # Получение данных из формы
        last_name = request.form['last_name']
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name', '') # Необязательное поле
        group_number = request.form.get('group_number', '') # Необязательное поле
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Проверка корректности username
        if not User.is_valid_email(username):
            flash(_('Некорректный формат email'))
            return render_template('auth/register.html')

        # Проверка совпадения паролей
        if password != confirm_password:
            flash(_('Пароли не совпадают'))
            return render_template('auth/register.html')

        # Проверка существования пользователя
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(_('Пользователь с таким логином уже существует'))
            return render_template('auth/register.html')

        # Создание нового студента
        new_user = User(
            username=username,
            password_hash=password,
            role='student',  # Все зарегистрированные пользователи - студенты
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            group_number=group_number
        )

        db.session.add(new_user)
        db.session.commit()

        flash(_('Регистрация прошла успешно'))
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@bp.route('/logout') # Маршрут для /logout относительно префикса Blueprint
@login_required
def logout():
    """
    Маршрут для выхода из системы
    """
    logout_user()
    session.clear()  # Очистка сессии
    return redirect(url_for('auth.login')) # Перенаправление на страницу входа

@bp.route('/change_language/<language>')
# УБРАНО: @login_required
def change_language(language):
    """
    Маршрут для изменения языка интерфейса

    Args:
        language (str): Код языка ('ru', 'en')
    """
    if language in Config.LANGUAGES:
        # Обновляем язык в сессии
        session['language'] = language

        # Если пользователь аутентифицирован, обновляем его профиль (опционально)
        if current_user.is_authenticated:
            current_user.language = language
            db.session.commit() # Зафиксируем изменение в БД

        flash(_('Язык интерфейса изменен')) # Используем _
    else:
        flash(_('Неподдерживаемый язык')) # Используем _

    # --- ИСПРАВЛЕННАЯ ЛОГИКА РЕДИРЕКТА ---
    # Получаем реферер
    referrer = request.referrer
    redirect_url = None

    # Проверяем, является ли реферер безопасным (наш домен)
    if referrer:
        ref_url_parsed = urlparse(referrer)
        # Проверяем, что реферер принадлежит нашему приложению (scheme и netloc совпадают)
        # или что он просто путь (относительный URL)
        if ref_url_parsed.netloc == request.host:
             # Убедимся, что URL не является URL-ом самого change_language (чтобы избежать цикла)
             # и не является URL-ом login (чтобы избежать возврата на login)
             ref_path = ref_url_parsed.path
             if not ref_path.endswith(url_for('auth.change_language', language='any_placeholder')) and not ref_path.endswith(url_for('auth.login')):
                 redirect_url = referrer

    # Если реферер не подходил или его не было, используем главную страницу
    if not redirect_url:
        redirect_url = url_for('main.index')
    # Выполняем редирект
    return redirect(redirect_url)
    # ------------------------------

@bp.route('/change_theme/<theme>')
@login_required
def change_theme(theme):
    """
    Маршрут для изменения темы оформления

    Args:
        theme (str): Название темы
    """
    import os
    import json

    # Проверка существования файла темы
    theme_file = os.path.join(Config.THEMES_PATH, f'{theme}.json')
    if os.path.exists(theme_file):
        current_user.theme = theme
        session['theme'] = theme
        db.session.commit()
        flash(_('Тема оформления изменена'))
    else:
        flash(_('Указанная тема не найдена'))

    return redirect(request.referrer or url_for('main.index'))