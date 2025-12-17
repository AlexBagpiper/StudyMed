# app/routes/admin.py (обновленный)
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test import Test
from app.models.question import Question
from app.models.annotation import ImageAnnotation
from werkzeug.utils import secure_filename
import os
import json
import cv2
import numpy as np
from app.utils.image_processing import process_coco_annotations, process_yolo_annotations

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

    tests = Test.query.all()
    annotations = ImageAnnotation.query.all()
    users = User.query.all()

    return render_template('admin/index.html',
                          tests=tests,
                          annotations=annotations,
                          users=users)

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

@bp.route('/create_test', methods=['POST'])
@login_required
def create_test():
    """
    Маршрут для создания нового теста

    Проверяет права доступа и создает новый тест
    """
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    title = request.form['title']
    description = request.form['description']

    new_test = Test(title=title, description=description, creator_id=current_user.id)
    db.session.add(new_test)
    db.session.commit()

    return redirect(url_for('admin.index'))

@bp.route('/add_question', methods=['POST'])
@login_required
def add_question():
    """
    Маршрут для добавления вопроса к тесту

    Проверяет права доступа и добавляет новый вопрос
    """
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    test_id = request.form['test_id']
    question_text = request.form['question_text']
    question_type = request.form['question_type']
    correct_answer = request.form['correct_answer']

    new_question = Question(
        test_id=test_id,
        question_text=question_text,
        question_type=question_type,
        correct_answer=correct_answer
    )
    db.session.add(new_question)
    db.session.commit()

    return jsonify({'success': True})

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

    # Проверка обязательных полей (фамилия и имя)
    if not last_name or not first_name:
        flash('Фамилия и имя обязательны для заполнения')
        return redirect(url_for('admin.index'))

    # Проверка совпадения паролей
    if password != confirm_password:
        flash('Пароли не совпадают')
        return redirect(url_for('admin.index'))

    # Проверка существования пользователя
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash('Пользователь с таким логином уже существует')
        return redirect(url_for('admin.index'))

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
    return redirect(url_for('admin.index'))

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