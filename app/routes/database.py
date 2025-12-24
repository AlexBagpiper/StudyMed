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
    """Главная страница управления базой данных — только для администраторов"""
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    stats = {
        'users': User.query.count(),
        'questions': Question.query.count(),
        'annotations': ImageAnnotation.query.count(),
        'results': TestResult.query.count(),
        'topics': TestTopic.query.count(),
    }

    return render_template('database/index.html', **stats)

# === Маршруты просмотра ===

@bp.route('/database/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    sort_by, order, per_page, page = _get_pagination_params()

    sort_fields = {
        'role': User.role,
        'first_name': User.first_name,
        'group_number': User.group_number,
        'date': User.created_at,
    }

    query = User.query
    query = _apply_sorting(query, User, sort_by, sort_fields, order, User.created_at)

    if per_page is None:
        users_list = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        users_list = pagination.items

    return render_template('database/users.html',
                          users=users_list,
                          pagination=pagination,
                          current_per_page=request.args.get('per_page', '10'))

@bp.route('/database/questions')
@login_required
def questions():
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    sort_by, order, per_page, page = _get_pagination_params()
    topics = TestTopic.query.all()
    topic_map = {t.id: t.name for t in topics}

    sort_fields = {
        'user': Question.creator_id,
        'topic': TestTopic.name,
        'type': Question.question_type,
        'date': Question.created_at,
    }

    query = Question.query.join(TestTopic, Question.topic_id == TestTopic.id)
    query = _apply_sorting(query, Question, sort_by, sort_fields, order, Question.created_at)

    if per_page is None:
        questions_list = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        questions_list = pagination.items

    return render_template('database/questions.html',
                          questions=questions_list,
                          topic_map=topic_map,
                          pagination=pagination,
                          current_per_page=request.args.get('per_page', '10'))


@bp.route('/database/topics')
@login_required
def topics():
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    sort_by, order, per_page, page = _get_pagination_params()

    sort_fields = {
        'id': TestTopic.id,
        'name': TestTopic.name,
        'date': TestTopic.created_at,
    }

    query = TestTopic.query
    query = _apply_sorting(query, TestTopic, sort_by, sort_fields, order, TestTopic.created_at)

    if per_page is None:
        topics_list = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        topics_list = pagination.items

    return render_template('database/topics.html',
                          topics=topics_list,
                          pagination=pagination,
                          current_per_page=request.args.get('per_page', '10'))


@bp.route('/database/annotations')
@login_required
def annotations():
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    sort_by, order, per_page, page = _get_pagination_params()

    sort_fields = {
        'id': ImageAnnotation.id,
        'image': ImageAnnotation.image_file,
        'annotation': ImageAnnotation.annotation_file,
        'format': ImageAnnotation.format_type,
        'date': ImageAnnotation.created_at,
    }

    query = ImageAnnotation.query
    query = _apply_sorting(query, ImageAnnotation, sort_by, sort_fields, order, ImageAnnotation.created_at)

    if per_page is None:
        annotations_list = query.all()
        pagination = None
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        annotations_list = pagination.items

    return render_template('database/annotations.html',
                          annotations=annotations_list,
                          pagination=pagination,
                          current_per_page=request.args.get('per_page', '10'))


@bp.route('/database/results')
@login_required
def results():
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    results_list = TestResult.query.all()
    return render_template('database/results.html', results=results_list)


# === Маршруты редактирования и удаления ===

@bp.route('/database/delete/<table>/<int:id>')
@login_required
def delete_record(table, id):
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    try:
        record = None
        if table == 'users':
            record = User.query.get_or_404(id)
        elif table == 'questions':
            record = Question.query.get_or_404(id)
        elif table == 'topics':
            record = TestTopic.query.get_or_404(id)
        elif table == 'annotations':
            record = ImageAnnotation.query.get_or_404(id)
            # Удаляем связанные файлы
            upload_folder = current_app.config.get('UPLOAD_FOLDER')
            if upload_folder:
                img_path = os.path.join(upload_folder, 'images', record.image_file)
                ann_path = os.path.join(upload_folder, 'annotations', record.annotation_file)
                for path in [img_path, ann_path]:
                    if os.path.isfile(path):
                        try:
                            os.remove(path)
                        except OSError as e:
                            current_app.logger.warning(f"Failed to delete file {path}: {e}")
        elif table == 'results':
            record = TestResult.query.get_or_404(id)
        else:
            flash(_('Недопустимая таблица: %(table)s', table=table))
            return redirect(url_for('database.index'))

        db.session.delete(record)
        db.session.commit()
        flash(_('Запись из таблицы "%(table)s" удалена', table=table))

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error deleting record")
        flash(_('Ошибка при удалении: %(error)s', error=str(e)))

    next_url = request.args.get('next')
    if not is_safe_url(next_url):
        next_url = url_for('database.index')

    return redirect(next_url)


@bp.route('/database/edit/<table>/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_record(table, id):
    if current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    # Получаем запись заранее для GET и POST
    record = None
    if table == 'users':
        record = User.query.get_or_404(id)
    elif table == 'questions':
        record = Question.query.get_or_404(id)
    elif table == 'topics':
        record = TestTopic.query.get_or_404(id)
    elif table == 'annotations':
        record = ImageAnnotation.query.get_or_404(id)
    elif table == 'results':
        record = TestResult.query.get_or_404(id)
    else:
        flash(_('Недопустимая таблица'))
        return redirect(url_for('database.index'))

    topics = TestTopic.query.all() if table in ('questions',) else None

    if request.method == 'POST':
        try:
            if table == 'users':
                record.username = request.form['username'].strip()
                record.role = request.form['role']
                record.language = request.form.get('language', 'ru')
                record.theme = request.form.get('theme', 'default')
                record.first_name = request.form.get('first_name', '').strip()
                record.last_name = request.form.get('last_name', '').strip()
                record.middle_name = request.form.get('middle_name', '').strip()
                record.group_number = request.form.get('group_number', '').strip()

            elif table == 'questions':
                record.topic_id = int(request.form['topic_id'])
                record.question_type = request.form['question_type']
                record.question_text = request.form['question_text'].strip()
                record.correct_answer = request.form.get('correct_answer', '').strip()

            elif table == 'topics':
                name = request.form['name'].strip()
                description = request.form.get('description', '').strip()
                if not name:
                    flash(_('Название темы обязательно'))
                    return render_template('database/edit_topic.html', topic=record)
                # Проверка уникальности
                existing = TestTopic.query.filter(
                    TestTopic.name == name,
                    TestTopic.id != id
                ).first()
                if existing:
                    flash(_('Тема с таким названием уже существует'))
                    return render_template('database/edit_topic.html', topic=record)
                record.name = name
                record.description = description

            elif table == 'annotations':
                record.image_file = request.form['image_file'].strip()
                record.annotation_file = request.form['annotation_file'].strip()
                record.format_type = request.form.get('format_type', 'coco')

            elif table == 'results':
                try:
                    record.score = float(request.form['score'])
                except (TypeError, ValueError):
                    flash(_('Некорректное значение балла'))
                    return render_template('database/edit_result.html', result=record)
                record.answers_json = request.form.get('answers_json', '{}').strip()
                record.metrics_json = request.form.get('metrics_json', '{}').strip()

            db.session.commit()
            flash(_('Запись успешно обновлена'))

            next_url = request.form.get('next') or request.args.get('next')
            if not is_safe_url(next_url):
                next_url = url_for('database.index')

            return redirect(next_url)

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Error updating record")
            flash(_('Ошибка при обновлении: %(error)s', error=str(e)))

    # GET: отображение формы
    template_map = {
        'users': 'database/edit_user.html',
        'questions': 'database/edit_question.html',
        'topics': 'database/edit_topic.html',
        'annotations': 'database/edit_annotation.html',
        'results': 'database/edit_result.html',
    }

    return render_template(
        template_map[table],
        **{table.rstrip('s'): record},  # передаём `user=record`, `question=record` и т.д.
        topics=topics
    )

# === Вспомогательные функции ===

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

def _get_pagination_params():
    """Получение параметров пагинации и сортировки из запроса"""
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    per_page_raw = request.args.get('per_page', '10')
    page = request.args.get('page', 1, type=int)

    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    return sort_by, order, per_page, page


def _apply_sorting(query, model, sort_by, sort_fields, order, default_field):
    """Применение сортировки к запросу"""
    sort_field = sort_fields.get(sort_by, default_field)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)
    return query.order_by(sort_expr)
