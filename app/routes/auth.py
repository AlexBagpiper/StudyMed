# app/routes/auth.py
"""
Маршруты аутентификации приложения медицинского тестирования
Содержит логику входа, регистрации и выхода пользователей
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from flask_babel import _
from urllib.parse import urlparse, urljoin
import os

# Создание Blueprint для маршрутов аутентификации
bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Маршрут для входа в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        # 🔑 Критически важно: используем хэширование!
        if user and user.check_password(password):
            login_user(user)

            # Восстанавливаем настройки из профиля
            session['language'] = user.language
            session['theme'] = user.theme

            # Редирект по роли
            if user.role == 'admin':
                next_page = url_for('admin.index')
            elif user.role == 'teacher':
                next_page = url_for('teacher.index')
            else:  # student
                next_page = url_for('student.view_tests')

            # Безопасный редирект с next
            next_arg = request.args.get('next')
            if next_arg and is_safe_url(next_arg):
                next_page = next_arg

            return redirect(next_page)
        else:
            flash(_('Неверные учетные данные'))

    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Маршрут для регистрации нового пользователя (студента)"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        last_name = request.form.get('last_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        middle_name = request.form.get('middle_name', '').strip()
        group_number = request.form.get('group_number', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Валидация
        if not User.is_valid_email(username):
            flash(_('Некорректный формат email'))
            return render_template('auth/register.html')

        if not last_name or not first_name:
            flash(_('Фамилия и имя обязательны'))
            return render_template('auth/register.html')

        if password != confirm_password:
            flash(_('Пароли не совпадают'))
            return render_template('auth/register.html')

        '''if len(password) < 6:
            flash(_('Пароль должен содержать не менее 6 символов'))
            return render_template('auth/register.html')'''

        if User.query.filter_by(username=username).first():
            flash(_('Пользователь с таким логином уже существует'))
            return render_template('auth/register.html')

        try:
            new_user = User(
                username=username,
                role='student',
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                group_number=group_number
            )
            new_user.set_password(password)  # ✅ хэшируем пароль

            db.session.add(new_user)
            db.session.commit()

            flash(_('Регистрация прошла успешно. Вы можете войти.'))
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Error during registration")
            flash(_('Ошибка при регистрации. Попробуйте позже.'))

    return render_template('auth/register.html')

@bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    session.clear()
    flash(_('Вы вышли из системы'))
    return redirect(url_for('auth.login'))


@bp.route('/change_language/<language>')
def change_language(language):
    """Изменение языка интерфейса (без авторизации — для публичных страниц)"""
    supported_langs = current_app.config.get('LANGUAGES', {})
    if language in supported_langs:
        session['language'] = language

        if current_user.is_authenticated:
            current_user.language = language
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        flash(_('Язык интерфейса изменён'))
    else:
        flash(_('Неподдерживаемый язык'))

    # Безопасный редирект: только локальные пути
    referrer = request.referrer
    if referrer and is_safe_url(referrer):
        # Избегаем зацикливания на /change_language/...
        parsed = urlparse(referrer)
        if not parsed.path.startswith('/auth/change_language/'):
            return redirect(referrer)

    return redirect(url_for('main.index'))


@bp.route('/change_theme/<theme>')
@login_required
def change_theme(theme):
    """Изменение темы оформления — только для авторизованных"""
    themes_path = current_app.config.get('THEMES_PATH')
    if not themes_path:
        flash(_('Темы не настроены'))
        return redirect(request.referrer or url_for('main.index'))

    # Нормализуем путь: если относительный — от корня приложения
    if not os.path.isabs(themes_path):
        themes_path = os.path.join(current_app.root_path, themes_path)

    theme_file = os.path.join(themes_path, f'{theme}.json')

    # Защита от path traversal
    if not os.path.abspath(theme_file).startswith(os.path.abspath(themes_path)):
        current_app.logger.warning(f"Theme path traversal attempt: {theme}")
        flash(_('Недопустимое название темы'))
        return redirect(request.referrer or url_for('main.index'))

    if os.path.isfile(theme_file):
        current_user.theme = theme
        session['theme'] = theme
        try:
            db.session.commit()
            flash(_('Тема оформления изменена'))
        except Exception:
            db.session.rollback()
            flash(_('Ошибка при сохранении темы'))
    else:
        flash(_('Указанная тема не найдена'))

    return redirect(request.referrer or url_for('main.index'))

# === Вспомогательные функции ===

def is_safe_url(target):
    """Проверка безопасности URL для редиректа"""
    if not target:
        return False

    host_url = request.host_url.rstrip('/')
    target_url = urljoin(host_url + '/', target).rstrip('/')

    ref = urlparse(host_url)
    test = urlparse(target_url)

    return (
        test.scheme in ('http', 'https') and
        ref.netloc == test.netloc and
        test.path.startswith('/')
    )