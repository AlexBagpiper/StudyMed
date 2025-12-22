# app/routes/admin.py (обновленный)
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test_topics import TestTopic
from app.models.question import Question
from app.models.annotation import ImageAnnotation
from werkzeug.utils import secure_filename
import os
import json
import cv2
import numpy as np
from app.utils.image_processing import process_coco_annotations, process_yolo_annotations
from flask_babel import _ # Импортируем _ для перевода flash-сообщений
from sqlalchemy import asc, desc

# Создание Blueprint для маршрутов администратора
# Теперь этот blueprint будет использовать префикс '/admin' при регистрации
bp = Blueprint('admin', __name__)

@bp.route('/') # Это теперь /admin/
@login_required
def index():
    """
    Главная страница администратора (доступна по /admin/)
    Проверяет права доступа и отображает панель управления
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        # Перенаправляем на главную, которая уже обработает аутентификацию
        return redirect(url_for('main.index'))

    annotations = ImageAnnotation.query.all()
    users = User.query.all()
    topics = TestTopic.query.all() # Добавляем темы

    return render_template('admin/index.html',
                          annotations=annotations,
                          users=users,
                          topics=topics)

@bp.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    """
    Маршрут для загрузки изображений с аннотациями

    Проверяет права доступа и обрабатывает загрузку файлов
    """
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    # Проверка наличия файлов
    if 'image' not in request.files or 'annotation' not in request.files:
        return jsonify({'error': 'Требуются оба файла: изображение и аннотация'}), 400

    image_file = request.files['image']
    annotation_file = request.files['annotation']

    if image_file.filename == '' or annotation_file.filename == '':
        return jsonify({'error': 'Файлы не выбраны'}), 400

    # Проверка разрешенных расширений
    from config import Config
    if not allowed_file(image_file.filename, Config.ALLOWED_IMAGE_EXTENSIONS) or \
       not allowed_file(annotation_file.filename, Config.ALLOWED_ANNOTATION_EXTENSIONS):
        return jsonify({'error': 'Неверный формат файла'}), 400

    try:
        # Сохранение файлов
        image_filename = secure_filename(image_file.filename)
        image_path = os.path.join(current_user.app.config['UPLOAD_FOLDER'], image_filename)
        image_file.save(image_path)

        annotation_filename = secure_filename(annotation_file.filename)
        annotation_path = os.path.join(current_user.app.config['UPLOAD_FOLDER'], annotation_filename)
        annotation_file.save(annotation_path)

        # Определение типа формата
        format_type = 'coco' if annotation_filename.endswith('.json') else 'yolo'

        # Обработка аннотаций
        if format_type == 'coco':
            processed_data = process_coco_annotations(annotation_path)
        else:  # YOLO
            img = cv2.imread(image_path)
            if img is None:
                return jsonify({'error': 'Не удалось загрузить изображение для обработки YOLO'}), 500
            processed_data = process_yolo_annotations(annotation_path, img.shape)

        if processed_data is None:
            return jsonify({'error': 'Не удалось обработать файл аннотации'}), 500

        # Создание новой аннотации
        new_annotation = ImageAnnotation(
            filename=image_filename,
            annotation_file=annotation_filename,
            format_type=format_type,
            labels=json.dumps(processed_data['labels'])
        )

        db.session.add(new_annotation)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Файлы успешно загружены',
            'id': new_annotation.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/teachers')
@login_required
def teachers():
    """
    Просмотр преподавателей (только для администраторов)
    """
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    # Параметры сортировки
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')

    # Параметр количества записей на странице
    per_page_raw = request.args.get('per_page', '10')
    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    # Поля сортировки
    sort_fields = {
        'username': User.username,
        'first_name': User.first_name,
        'last_name': User.last_name,
        'date': User.created_at
    }
    sort_field = sort_fields.get(sort_by, User.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    # Запрос только преподавателей
    query = User.query.filter_by(role='teacher').order_by(sort_expr)

    # Пагинация или выбор всех
    page = request.args.get('page', 1, type=int)

    if per_page is None:
        users = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        users = pagination.items

    return render_template('admin/teachers.html',
                          users=users,
                          pagination=pagination,
                          current_per_page=per_page_raw)


@bp.route('/create_teacher', methods=['POST'])
@login_required
def create_teacher():
    """
    Маршрут для создания преподавателя с указанием ФИО

    Проверяет права доступа и создает нового преподавателя
    """
    if current_user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    # Получение данных из формы
    last_name = request.form.get('last_name', '').strip()
    first_name = request.form.get('first_name', '').strip()
    middle_name = request.form.get('middle_name', '').strip()
    group_number = request.form.get('group_number', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    # Проверка корректности username
    if not User.is_valid_email(username):
        flash(_('Некорректный формат email'))
        return redirect(url_for('admin.teachers'))

    # Проверка обязательных полей (фамилия и имя)
    if not last_name or not first_name:
        flash(_('Фамилия и имя обязательны для заполнения'))
        return redirect(url_for('admin.teachers'))

    # Проверка совпадения паролей
    if password != confirm_password:
        flash(_('Пароли не совпадают'))
        return redirect(url_for('admin.teachers'))

    # Проверка существования пользователя
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash(_('Пользователь с таким логином уже существует'))
        return redirect(url_for('admin.teachers'))

    # Создание нового преподавателя
    new_teacher = User(
        username=username,
        password_hash=password,
        role='teacher',
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        group_number=group_number
    )

    db.session.add(new_teacher)
    db.session.commit()

    flash(f'Преподаватель {new_teacher.get_formatted_name()} успешно создан')
    return redirect(url_for('admin.teachers'))

@bp.route('/topics')
@login_required
def topics():
    """
    Управление темами тестов (только для администраторов)
    """
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    # Параметры сортировки
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')

    # Параметр количества записей
    per_page_raw = request.args.get('per_page', '10')
    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    # Поля сортировки
    sort_fields = {
        'id': TestTopic.id,
        'name': TestTopic.name,
        'date': TestTopic.created_at
    }
    sort_field = sort_fields.get(sort_by, TestTopic.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    # Запрос
    query = TestTopic.query.order_by(sort_expr)

    # Пагинация или выбор всех
    page = request.args.get('page', 1, type=int)

    if per_page is None:
        topics = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        topics = pagination.items

    return render_template('admin/topics.html',
                          topics=topics,
                          pagination=pagination,
                          current_per_page=per_page_raw)

@bp.route('/create_topic', methods=['POST'])
@login_required
def create_topic():
    """
    Маршрут для создания новой темы теста
    """
    if current_user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    name = request.form['name']
    description = request.form.get('description', '')

    # Проверка уникальности имени темы
    existing_topic = TestTopic.query.filter_by(name=name).first()
    if existing_topic:
        flash(_('Тема с таким названием уже существует'))
        return redirect(url_for('admin.index'))

    new_topic = TestTopic(name=name, description=description)
    db.session.add(new_topic)
    db.session.commit()

    flash(_('Тема создана успешно'))
    return redirect(url_for('admin.topics'))

@bp.route('/edit_topic/<int:topic_id>', methods=['POST'])
@login_required
def edit_topic(topic_id):
    """
    Маршрут для редактирования темы теста

    Args:
        topic_id (int): ID темы
    """
    if current_user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    topic = TestTopic.query.get_or_404(topic_id)
    topic.name = request.form['name']
    topic.description = request.form.get('description', '')
    db.session.commit()

    flash(_('Тема обновлена успешно'))
    return redirect(url_for('admin.topics'))

@bp.route('/delete_topic/<int:topic_id>')
@login_required
def delete_topic(topic_id):
    """
    Маршрут для удаления темы теста

    Args:
        topic_id (int): ID темы
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('admin.index'))

    topic = TestTopic.query.get_or_404(topic_id)

    db.session.delete(topic)
    db.session.commit()

    flash(_('Тема удалена успешно'))
    return redirect(url_for('admin.topics'))

def allowed_file(filename, extensions_set):
    """
    Проверка разрешенного расширения файла

    Args:
        filename (str): Имя файла
        extensions_set (set): Множество разрешенных расширений

    Returns:
        bool: True если расширение разрешено, иначе False
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in extensions_set