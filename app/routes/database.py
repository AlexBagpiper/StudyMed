# app/routes/database.py
"""
Маршруты для просмотра и управления базой данных
Содержит инструменты просмотра и редактирования данных в БД
"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test_topics import TestTopic
from app.models.question import Question
from app.models.annotation import ImageAnnotation, TestResult
from sqlalchemy import asc, desc
from urllib.parse import urlparse, urljoin
from flask_babel import _ # Импортируем _ для перевода flash-сообщений

# Создание Blueprint для маршрутов управления БД
bp = Blueprint('database', __name__)

@bp.route('/database')
@login_required
def index():
    """
    Главная страница управления базой данных
    Только для администраторов
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

    # Получение статистики по таблицам
    users_count = User.query.count()
    questions_count = Question.query.count()
    annotations_count = ImageAnnotation.query.count()
    results_count = TestResult.query.count()
    topics_count = TestTopic.query.count()

    return render_template('database/index.html',
                          users_count=users_count,
                          questions_count=questions_count,
                          annotations_count=annotations_count,
                          results_count=results_count,
                          topics_count=topics_count)

@bp.route('/users')
@login_required
def users():
    """
    Просмотр пользователей
    """

    # Получаем параметры сортировки из запроса
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')

    if current_user.role not in ['admin']:
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Параметр количества записей на странице
    per_page_raw = request.args.get('per_page', '10')
    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    # Определяем поля сортировки
    sort_fields = {
        'role': User.role,
        'first_name': User.first_name,
        'group_number': User.group_number,
        'date': User.created_at
    }

    # Получаем поле для сортировки
    sort_field = sort_fields.get(sort_by, User.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    if current_user.role == 'admin':
        query = User.query.order_by(sort_expr)
    else:
        return redirect(url_for('main.index'))

    # Пагинация или выбор всех
    page = request.args.get('page', 1, type=int)

    # Пагинация
    if per_page is None:
        # Показываем все записи
        users = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        users = pagination.items

    return render_template('database/users.html',
                            users=users,
                            pagination=pagination,
                            current_per_page=per_page_raw)  # передаём текущее значение для select


@bp.route('/questions')
@login_required
def questions():
    """
    Маршрут для просмотра созданных тестов
    """
    # Получаем параметры сортировки из запроса
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')

    topics = TestTopic.query.all()
    topic_map = {topic.id: topic.name for topic in topics}  # ← остаётся в памяти как dict

    if current_user.role not in ['admin']:
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Параметр количества записей на странице
    per_page_raw = request.args.get('per_page', '10')
    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    # Определяем поля сортировки
    sort_fields = {
        'user': Question.creator_id,
        'topic': TestTopic.name,
        'type': Question.question_type,
        'date': Question.created_at
    }

    # Получаем поле для сортировки
    sort_field = sort_fields.get(sort_by, Question.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    # Преподаватель видит только свои тесты, администратор - все
    if current_user.role == 'admin':
        query = Question.query.join(TestTopic, Question.topic_id == TestTopic.id).order_by(sort_expr)
    else:
        return redirect(url_for('main.index'))

    # Пагинация или выбор всех
    page = request.args.get('page', 1, type=int)

    # Пагинация
    if per_page is None:
        # Показываем все записи
        questions = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        questions = pagination.items

    return render_template('database/questions.html',
                            questions=questions,
                            topic_map=topic_map,
                            pagination=pagination,
                            current_per_page=per_page_raw)  # передаём текущее значение для select

@bp.route('/topics')
@login_required
def topics():
    """
    Просмотр тем тестов (только для администраторов)
    """
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    # Параметры
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    per_page_raw = request.args.get('per_page', '10')
    page = request.args.get('page', 1, type=int)

    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    # Сортировка
    sort_fields = {
        'id': TestTopic.id,
        'name': TestTopic.name,
        'date': TestTopic.created_at
    }
    sort_field = sort_fields.get(sort_by, TestTopic.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    query = TestTopic.query.order_by(sort_expr)

    # Пагинация
    if per_page is None:
        topics = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        topics = pagination.items

    return render_template('database/topics.html',
                          topics=topics,
                          pagination=pagination,
                          current_per_page=per_page_raw)

@bp.route('/database/annotations')
@login_required
def annotations():
    """
    Просмотр аннотаций с пагинацией и сортировкой (только для админа)
    """
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.dashboard'))

    # Параметры
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    per_page_raw = request.args.get('per_page', '10')
    page = request.args.get('page', 1, type=int)

    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    # Поля сортировки
    sort_fields = {
        'id': ImageAnnotation.id,
        'image': ImageAnnotation.image_file,
        'annotation': ImageAnnotation.annotation_file,
        'format': ImageAnnotation.format_type,
        'date': ImageAnnotation.created_at
    }
    sort_field = sort_fields.get(sort_by, ImageAnnotation.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    query = ImageAnnotation.query.order_by(sort_expr)

    # Пагинация
    if per_page is None:
        annotations = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        annotations = pagination.items

    return render_template('database/annotations.html',
                          annotations=annotations,
                          pagination=pagination,
                          current_per_page=per_page_raw)

@bp.route('/database/results')
@login_required
def results():
    """
    Просмотр результатов тестов
    """
    if current_user.role != 'admin':
        flash(_('Доступ запрещен'))
        return redirect(url_for('main.index'))

    results = TestResult.query.all()
    return render_template('database/results.html', results=results)

@bp.route('/database/delete/<table>/<int:id>')
@login_required
def delete_record(table, id):
    """
    Удаление записи из таблицы

    Args:
        table (str): Название таблицы
        id (int): ID записи
    """
    if current_user.role != 'admin':
        flash(_('Доступ запрещен'))
        return redirect(url_for('main.dashboard'))

    try:
        if table == 'users':
            record = User.query.get_or_404(id)
        elif table == 'questions':
            record = Question.query.get_or_404(id)
        elif table == 'topics':
            record = TestTopic.query.get_or_404(id)
        elif table == 'annotations':
            record = ImageAnnotation.query.get_or_404(id)
            # Удаляем файлы
            upload_folder = current_app.config['UPLOAD_FOLDER']
            image_path = os.path.join(upload_folder, 'images', record.image_file)
            annotation_path = os.path.join(upload_folder, 'annotations', record.annotation_file)
            # Удаляем файлы (игнорируем, если не найдены)
            for path in [image_path, annotation_path]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError as e:
                    pass
        elif table == 'results':
            record = TestResult.query.get_or_404(id)
        else:
            flash('Неверная таблица')
            return redirect(url_for('database.index'))
        db.session.delete(record)
        db.session.commit()
        flash(f'Запись из таблицы {table} удалена')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении: {str(e)}')

    next_url = request.args.get('next')
    if not is_safe_url(next_url):
        next_url = None

    return redirect(next_url or url_for(f'database.{table[:-1] if table.endswith("s") else table}s'))


@bp.route('/database/edit/<table>/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_record(table, id):
    """
    Редактирование записи в таблице

    Args:
        table (str): Название таблицы
        id (int): ID записи
    """

    topics = TestTopic.query.all()

    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        try:
            if table == 'users':
                record = User.query.get_or_404(id)
                record.username = request.form['username']
                record.role = request.form['role']
                record.language = request.form['language']
                record.theme = request.form['theme']
                record.first_name = request.form['first_name']
                record.last_name = request.form['last_name']
                record.middle_name = request.form['middle_name']
                record.group_number = request.form['group_number']
            elif table == 'questions':
                record = Question.query.get_or_404(id)
                record.topic_id = request.form['topic_id']
                record.question_type = request.form['question_type']
                record.question_text = request.form['question_text']
                record.correct_answer = request.form['correct_answer']
                record.question_text = request.form['question_text']
            elif table == 'topics':
                record = TestTopic.query.get_or_404(id)
                name = request.form['name'].strip()
                description = request.form.get('description', '').strip()
                if not name:
                    flash(_('Название темы обязательно'))
                    return redirect(url_for('database.edit_record', table='topics', id=id))
                # Проверка уникальности (кроме текущей)
                existing = TestTopic.query.filter(
                    TestTopic.name == name,
                    TestTopic.id != id
                ).first()
                if existing:
                    flash(_('Тема с таким названием уже существует'))
                    return redirect(url_for('database.edit_record', table='topics', id=id))
                record.name = name
                record.description = description
            elif table == 'annotations':
                record = ImageAnnotation.query.get_or_404(id)
                record.filename = request.form['filename']
                record.annotation_file = request.form['annotation_file']
                record.format_type = request.form['format_type']
            elif table == 'results':
                record = TestResult.query.get_or_404(id)
                record.score = float(request.form['score'])
                record.answers_json = request.form['answers_json']
                record.metrics_json = request.form['metrics_json']
            else:
                flash('Неверная таблица')
                return redirect(url_for('database.index'))

            db.session.commit()
            flash(f'Запись в таблице {table} обновлена')

            next_url = request.form.get('next') or request.args.get('next')
            if not is_safe_url(next_url):
                next_url = None

            return redirect(next_url or url_for(f'database.{table[:-1] if table.endswith("s") else table}s'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении: {str(e)}')

    # Отображение формы редактирования
    if table == 'users':
        record = User.query.get_or_404(id)
        return render_template('database/edit_user.html', user=record)
    elif table == 'questions':
        record = Question.query.get_or_404(id)
        return render_template('database/edit_question.html', question=record, topics=topics)
    elif table == 'topics':  # ← ДОБАВЛЕНО
        record = TestTopic.query.get_or_404(id)
        return render_template('database/edit_topic.html', topic=record)
    elif table == 'annotations':
        record = ImageAnnotation.query.get_or_404(id)
        return render_template('database/edit_annotation.html', annotation=record)
    elif table == 'results':
        record = TestResult.query.get_or_404(id)
        return render_template('database/edit_result.html', result=record)
    else:
        flash('Неверная таблица')
        return redirect(url_for('database.index'))

def is_safe_url(target):
    """
    Проверяет, что target — безопасный локальный URL.
    Поддерживает относительные пути ('/admin') и абсолютные локальные URLы
    ('http://127.0.0.1:5000/admin').
    """
    if not target:
        return False

    # Приводим target к абсолютному URL относительно host_url
    # Это нормализует как '/path', так и 'http://host/path'
    host_url = request.host_url.rstrip('/')  # 'http://127.0.0.1:5000'
    target_url = urljoin(host_url + '/', target).rstrip('/')
    # → 'http://127.0.0.1:5000/admin/teachers'

    ref = urlparse(host_url)
    test = urlparse(target_url)

    # Проверяем: тот же протокол (http/https) и тот же хост:порт
    return (
        test.scheme in ('http', 'https') and
        ref.netloc == test.netloc and
        test.path.startswith('/')  # защита от 'javascript:'
    )