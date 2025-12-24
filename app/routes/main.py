"""
Основные маршруты приложения медицинского тестирования
Содержит главную страницу и общие маршруты
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory, abort, current_app
from flask_login import login_required, current_user
from app.models.user import User
from flask_babel import _, get_locale
from app import db
import os
import logging

# Создание Blueprint для основных маршрутов
bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """
    Главная страница приложения - перенаправление на вход или панель
    """
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.index'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher.index'))
        else:  # student
            return redirect(url_for('student.view_tests'))
    else:
        return redirect(url_for('auth.login'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Маршрут для просмотра и редактирования профиля пользователя
    Включает смену пароля (только при вводе текущего пароля)
    """
    if request.method == 'POST':
        # 1. Основные данные
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        middle_name = request.form.get('middle_name', '').strip()
        group_number = request.form.get('group_number', '').strip()
        language = request.form.get('language', current_user.language)
        theme = request.form.get('theme', current_user.theme)

        # Валидация языка
        supported_languages = current_app.config.get('LANGUAGES', {})
        if language not in supported_languages:
            flash(_('Неподдерживаемый язык'))
            return render_template('main/profile.html', user=current_user)

        # Валидация темы
        themes_path = current_app.config.get('THEMES_PATH')
        if themes_path:
            if not os.path.isabs(themes_path):
                themes_path = os.path.join(current_app.root_path, themes_path)
            theme_file = os.path.join(themes_path, f'{theme}.json')
            if not os.path.exists(theme_file):
                flash(_('Указанная тема не найдена'))
                return render_template('main/profile.html', user=current_user)

        # 2. Обновление пароля (если запрошено)
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        password_changed = False
        if current_password:
            # Пользователь хочет сменить пароль
            if not current_user.check_password(current_password):
                flash(_('Текущий пароль введён неверно'))
                return render_template('main/profile.html', user=current_user)

            if not new_password:
                flash(_('Новый пароль не может быть пустым'))
                return render_template('main/profile.html', user=current_user)

            '''if len(new_password) < 6:
                flash(_('Пароль должен содержать не менее 6 символов'))
                return render_template('main/profile.html', user=current_user)'''

            if new_password != confirm_password:
                flash(_('Новые пароли не совпадают'))
                return render_template('main/profile.html', user=current_user)

            # ✅ Успешная валидация — меняем пароль
            current_user.set_password(new_password)
            password_changed = True

        # 3. Сохранение изменений профиля
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
            messages = [_('Профиль успешно обновлён')]
            if password_changed:
                messages.append(_('Пароль изменён'))
            flash(' '.join(messages))
            return redirect(url_for('main.profile'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Profile update error: {e}")
            flash(_('Ошибка при обновлении профиля'))

    # GET: отображение формы
    return render_template('main/profile.html', user=current_user)


@bp.route('/uploads/<folder>/<filename>')
@login_required
def uploaded_file(folder, filename):
    """
    Маршрут для обслуживания загруженных файлов
    Внимание: если файлы должны быть приватными — добавьте проверку прав!
    """
    allowed_folders = {'images', 'annotations'}
    if folder not in allowed_folders:
        abort(404)

    # Получаем UPLOAD_FOLDER из конфига (абсолютный или относительный)
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        current_app.logger.error("UPLOAD_FOLDER not set in config")
        abort(500)

    # Приводим к абсолютному пути относительно корня приложения, если нужно
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, upload_folder)

    # Формируем путь к подпапке
    target_dir = os.path.join(upload_folder, folder)

    # Защита от path traversal: убеждаемся, что target_dir внутри upload_folder
    upload_folder_abs = os.path.abspath(upload_folder)
    target_dir_abs = os.path.abspath(target_dir)
    if not target_dir_abs.startswith(upload_folder_abs):
        current_app.logger.warning(f"Path traversal attempt: {folder}/{filename}")
        abort(403)

    # Логирование (в debug-режиме)
    if current_app.debug:
        current_app.logger.debug(f"Serving file from: {target_dir_abs}/{filename}")

    # Отдаём файл
    try:
        return send_from_directory(target_dir, filename)
    except FileNotFoundError:
        current_app.logger.warning(f"File not found: {os.path.join(target_dir_abs, filename)}")
        abort(404)
    except Exception as e:
        current_app.logger.error(f"Error serving file {folder}/{filename}: {e}")
        abort(500)