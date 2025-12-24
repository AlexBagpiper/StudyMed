"""
Маршруты администратора приложения медицинского тестирования
Содержит управление пользователями, темами и загрузку аннотаций
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test_topics import TestTopic
from app.models.annotation import ImageAnnotation
from werkzeug.utils import secure_filename
import os
import json
import cv2
import numpy as np
from app.utils.image_processing import process_coco_annotations  # убедитесь, что process_yolo_annotations тоже есть
from flask_babel import _
from sqlalchemy import asc, desc

# Создание Blueprint для маршрутов администратора
bp = Blueprint('admin', __name__)


@bp.route('/')
@login_required
def index():
    """Главная страница администратора"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    annotations = ImageAnnotation.query.all()
    users = User.query.all()
    topics = TestTopic.query.all()

    return render_template('admin/index.html',
                          annotations=annotations,
                          users=users,
                          topics=topics)


@bp.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    """Загрузка изображения и аннотации (для админа и преподавателя)"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': _('Доступ запрещён')}), 403

    if 'image' not in request.files or 'annotation' not in request.files:
        return jsonify({'error': _('Требуются оба файла: изображение и аннотация')}), 400

    image_file = request.files['image']
    annotation_file = request.files['annotation']

    if not image_file.filename or not annotation_file.filename:
        return jsonify({'error': _('Файлы не выбраны')}), 400

    # Получаем разрешённые расширения из конфига
    allowed_image_ext = set(current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg'}))
    allowed_ann_ext = set(current_app.config.get('ALLOWED_ANNOTATION_EXTENSIONS', {'json', 'txt'}))

    if not allowed_file(image_file.filename, allowed_image_ext) or \
       not allowed_file(annotation_file.filename, allowed_ann_ext):
        return jsonify({'error': _('Неверный формат файла')}), 400

    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            current_app.logger.error("UPLOAD_FOLDER not configured")
            return jsonify({'error': _('Серверная ошибка: папка загрузки не настроена')}), 500

        # Безопасные имена
        image_filename = secure_filename(image_file.filename)
        annotation_filename = secure_filename(annotation_file.filename)

        image_path = os.path.join(upload_folder, 'images', image_filename)
        annotation_path = os.path.join(upload_folder, 'annotations', annotation_filename)

        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        os.makedirs(os.path.dirname(annotation_path), exist_ok=True)

        # Сохранение
        image_file.save(image_path)
        annotation_file.save(annotation_path)

        # Определение формата
        format_type = 'coco' if annotation_filename.endswith('.json') else 'yolo'

        # Обработка аннотаций
        if format_type == 'coco':
            processed_data = process_coco_annotations(annotation_path)
        else:
            # Для YOLO — нужно изображение для получения размеров
            img = cv2.imread(image_path)
            if img is None:
                # Удаляем временные файлы
                for p in [image_path, annotation_path]:
                    if os.path.exists(p):
                        os.remove(p)
                return jsonify({'error': _('Не удалось загрузить изображение для обработки YOLO')}), 500

            # Предполагается, что у вас есть process_yolo_annotations
            try:
                from app.utils.image_processing import process_yolo_annotations
                processed_data = process_yolo_annotations(annotation_path, img.shape)
            except ImportError:
                current_app.logger.warning("process_yolo_annotations not implemented")
                processed_data = {'labels': []}

        if processed_data is None:
            # Очистка при ошибке
            for p in [image_path, annotation_path]:
                if os.path.exists(p):
                    os.remove(p)
            return jsonify({'error': _('Не удалось обработать файл аннотации')}), 500

        # Создание записи в БД
        new_annotation = ImageAnnotation(
            image_file=image_filename,          # ← исправлено: у вас в модели, скорее всего, `image_file`, а не `filename`
            annotation_file=annotation_filename,
            format_type=format_type,
            labels=json.dumps(processed_data.get('labels', []))
        )

        db.session.add(new_annotation)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': _('Файлы успешно загружены'),
            'id': new_annotation.id
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error in upload_image")
        # Пытаемся удалить временные файлы при ошибке
        try:
            for p in [image_path, annotation_path]:
                if os.path.exists(p):
                    os.remove(p)
        except Exception:
            pass
        return jsonify({'error': str(e)}), 500


@bp.route('/teachers')
@login_required
def teachers():
    """Просмотр преподавателей — только для админа"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    per_page_raw = request.args.get('per_page', '10')
    page = request.args.get('page', 1, type=int)

    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    sort_fields = {
        'username': User.username,
        'first_name': User.first_name,
        'last_name': User.last_name,
        'date': User.created_at
    }

    sort_field = sort_fields.get(sort_by, User.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    query = User.query.filter_by(role='teacher').order_by(sort_expr)

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
    """Создание преподавателя — только для админа"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('admin.teachers'))

    last_name = request.form.get('last_name', '').strip()
    first_name = request.form.get('first_name', '').strip()
    middle_name = request.form.get('middle_name', '').strip()
    group_number = request.form.get('group_number', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    # Валидация
    if not User.is_valid_email(username):
        flash(_('Некорректный формат email'))
        return redirect(url_for('admin.teachers'))

    if not last_name or not first_name:
        flash(_('Фамилия и имя обязательны для заполнения'))
        return redirect(url_for('admin.teachers'))

    if password != confirm_password:
        flash(_('Пароли не совпадают'))
        return redirect(url_for('admin.teachers'))

    if User.query.filter_by(username=username).first():
        flash(_('Пользователь с таким логином уже существует'))
        return redirect(url_for('admin.teachers'))

    try:
        new_teacher = User(
            username=username,
            role='teacher',
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            group_number=group_number
        )
        new_teacher.set_password(password)

        db.session.add(new_teacher)
        db.session.commit()

        flash(_('Преподаватель %(name)s успешно создан', name=new_teacher.get_formatted_name()))
        return redirect(url_for('admin.teachers'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error creating teacher")
        flash(_('Ошибка при создании преподавателя'))
        return redirect(url_for('admin.teachers'))


@bp.route('/topics')
@login_required
def topics():
    """Управление темами тестов — только для админа"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    per_page_raw = request.args.get('per_page', '10')
    page = request.args.get('page', 1, type=int)

    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    sort_fields = {
        'id': TestTopic.id,
        'name': TestTopic.name,
        'date': TestTopic.created_at
    }
    sort_field = sort_fields.get(sort_by, TestTopic.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    query = TestTopic.query.order_by(sort_expr)

    if per_page is None:
        topics_list = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        topics_list = pagination.items

    return render_template('admin/topics.html',
                          topics=topics_list,
                          pagination=pagination,
                          current_per_page=per_page_raw)


@bp.route('/create_topic', methods=['POST'])
@login_required
def create_topic():
    """Создание темы — только для админа"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('admin.topics'))

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash(_('Название темы обязательно'))
        return redirect(url_for('admin.topics'))

    if TestTopic.query.filter_by(name=name).first():
        flash(_('Тема с таким названием уже существует'))
        return redirect(url_for('admin.topics'))

    try:
        new_topic = TestTopic(name=name, description=description)
        db.session.add(new_topic)
        db.session.commit()
        flash(_('Тема "%(name)s" создана успешно', name=name))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error creating topic")
        flash(_('Ошибка при создании темы'))

    return redirect(url_for('admin.topics'))


@bp.route('/edit_topic/<int:topic_id>', methods=['POST'])
@login_required
def edit_topic(topic_id):
    """Редактирование темы — только для админа"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('admin.topics'))

    topic = TestTopic.query.get_or_404(topic_id)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash(_('Название темы обязательно'))
        return redirect(url_for('admin.topics'))

    # Проверка уникальности (кроме себя)
    existing = TestTopic.query.filter(
        TestTopic.name == name,
        TestTopic.id != topic_id
    ).first()
    if existing:
        flash(_('Тема с таким названием уже существует'))
        return redirect(url_for('admin.topics'))

    try:
        topic.name = name
        topic.description = description
        db.session.commit()
        flash(_('Тема успешно обновлена'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error editing topic")
        flash(_('Ошибка при обновлении темы'))

    return redirect(url_for('admin.topics'))


@bp.route('/delete_topic/<int:topic_id>')
@login_required
def delete_topic(topic_id):
    """Удаление темы — только для админа"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('admin.topics'))

    topic = TestTopic.query.get_or_404(topic_id)

    try:
        db.session.delete(topic)
        db.session.commit()
        flash(_('Тема удалена успешно'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error deleting topic")
        flash(_('Ошибка при удалении темы'))

    return redirect(url_for('admin.topics'))


# === Вспомогательные функции ===

def allowed_file(filename, extensions_set):
    """Проверка разрешённого расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions_set