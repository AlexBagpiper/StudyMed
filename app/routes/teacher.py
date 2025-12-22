# app/routes/teacher.py (новый файл)
"""
Маршруты преподавателя приложения медицинского тестирования
Содержит логику управления тестами, просмотра результатов и конструктора
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test_topics import TestTopic
from app.models.question import Question
from app.models.annotation import ImageAnnotation, TestResult
from app.models.user import User
from werkzeug.utils import secure_filename
import os
import json
import cv2
import numpy as np
from app.utils.image_processing import process_coco_annotations, process_yolo_annotations
from config import Config
from sqlalchemy import asc, desc
from urllib.parse import urlparse, urljoin
from flask_babel import _ # Импортируем _ для перевода flash-сообщений

# Создание Blueprint для маршрутов преподавателя
bp = Blueprint('teacher', __name__)

@bp.route('/teacher')
@login_required
def index():
    """
    Главная страница преподавателя - отображает меню
    """
    # Преподаватель видит только свои тесты (или все, если админ)
    '''if current_user.role == 'admin':
        tests = Test.query.all()
    else:
        tests = Test.query.filter_by(creator_id=current_user.id).all()'''

    return render_template('teacher/index.html')

@bp.route('/teacher/create_question', methods=['GET', 'POST'])
@login_required
def create_question():
    """
    Маршрут для создания нового вопроса (добавления в базу вопросов)
    Только для преподавателей и администраторов

    GET: Отображает форму создания вопроса
    POST: Обрабатывает данные формы и создает вопрос
    """
    if current_user.role not in ['admin', 'teacher']:
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))
    topics = TestTopic.query.all()
    if request.method == 'POST':
        question_text = request.form['question_text']
        question_type = request.form['question_type']
        topic_id = request.form['topic_id']

        # Создание нового вопроса
        new_question = Question(
            question_text=question_text,
            question_type=question_type,
            topic_id=topic_id,
            creator_id=current_user.id
        )

        if question_type == 'graphic':
            # Обработка загрузки изображения и аннотации
            image_file = request.files.get('image_file')
            annotation_file = request.files.get('annotation_file')

            if not image_file or not annotation_file:
                flash('Для графических вопросов требуются файлы изображения и аннотации')
                return render_template('teacher/create_question.html', topics=topics)

            # Проверка расширений
            from config import Config
            if not allowed_file(image_file.filename, Config.ALLOWED_IMAGE_EXTENSIONS) or \
               not allowed_file(annotation_file.filename, Config.ALLOWED_ANNOTATION_EXTENSIONS):
                flash('Неверный формат файла')
                return render_template('teacher/create_question.html', topics=topics)

            try:
                # Сохранение файлов
                image_filename = secure_filename(image_file.filename)
                annotation_filename = secure_filename(annotation_file.filename)

                # Создание уникальных имен файлов (опционально)
                import uuid
                unique_id = str(uuid.uuid4())[:8]
                name_part_img, ext_part_img = os.path.splitext(image_filename)
                name_part_ann, ext_part_ann = os.path.splitext(annotation_filename)
                image_filename = f"{name_part_img}_{unique_id}{ext_part_img}"
                annotation_filename = f"{name_part_ann}_{unique_id}{ext_part_ann}"

                upload_folder = current_app.config['UPLOAD_FOLDER']
                image_path = os.path.join(upload_folder, 'images', image_filename)
                annotation_path = os.path.join(upload_folder, 'annotations', annotation_filename)

                # Создание подкаталогов если не существуют
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                os.makedirs(os.path.dirname(annotation_path), exist_ok=True)

                image_file.save(image_path)
                annotation_file.save(annotation_path)

                # Определение типа формата
                format_type = 'coco' if annotation_filename.endswith('.json') else 'yolo'

                # Обработка аннотаций
                if format_type == 'coco':
                    processed_data = process_coco_annotations(annotation_path)
                else:  # YOLO
                    img = cv2.imread(image_path)
                    if img is None:
                        flash('Не удалось загрузить изображение для обработки YOLO')
                        return render_template('teacher/create_question.html', topics=topics)
                    processed_data = process_yolo_annotations(annotation_path, img.shape)

                if processed_data is None:
                    flash('Не удалось обработать файл аннотации')
                    return render_template('teacher/create_question.html', topics=topics)

                # Создание новой аннотации
                new_annotation = ImageAnnotation(
                    image_file=image_filename,
                    annotation_file=annotation_filename,
                    format_type=format_type,
                    labels=json.dumps(processed_data['labels'])
                )

                db.session.add(new_annotation)
                db.session.flush() # Получаем ID новой аннотации до коммита основного вопроса

                # Связываем вопрос с аннотацией
                new_question.image_annotation_id = new_annotation.id
                # Для графических вопросов, correct_answer может содержать ID аннотации
                # или использоваться image_annotation_id. В данном случае используем image_annotation_id.
                # Если нужно хранить ID в correct_answer, раскомментируйте следующую строку:
                # new_question.correct_answer = str(new_annotation.id)

            except Exception as e:
                print(e)
                db.session.rollback()
                flash(f'Ошибка при загрузке файлов: {str(e)}')
                return render_template('teacher/create_question.html', topics=topics)

        elif question_type == 'open':
            # Для текстовых вопросов сохраняем ответ
            correct_answer = request.form.get('correct_answer', '')
            new_question.correct_answer = correct_answer

        # Сохранение вопроса в базу данных
        db.session.add(new_question)
        db.session.commit()

        flash('Вопрос успешно создан')
        return redirect(url_for('teacher.view_questions')) # Перенаправляем на список вопросов

    return render_template('teacher/create_question.html', topics=topics)

@bp.route('/teacher/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    """
    Маршрут для редактирования вопроса
    Только для преподавателей и администраторов
    """
    if current_user.role not in ['admin', 'teacher']:
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    question = Question.query.get_or_404(question_id)
    topics = TestTopic.query.all()

    # Проверка прав доступа (только админ или создатель теста, к которому принадлежит вопрос)
    if question.creator_id != current_user.id and current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('teacher.view_questions'))

    if request.method == 'POST':
        question.topic_id = request.form['topic_id']
        question.question_text = request.form['question_text']
        question.question_type = request.form['question_type']

        if question.question_type == 'open':
            question.correct_answer = request.form.get('correct_answer', '')
            # Убираем связь с изображением для текстовых вопросов
            question.image_annotation_id = None
        elif question.question_type == 'graphic':
            # Обработка графического вопроса
            # В простом варианте, мы не меняем изображение/аннотацию, только текст вопроса
            # Если нужно изменить изображение/аннотацию, потребуется более сложная логика
            new_image_file = request.files.get('image_file')
            new_annotation_file = request.files.get('annotation_file')

            if new_image_file and new_annotation_file:
                # Проверка расширений
                if not allowed_file(new_image_file.filename, Config.ALLOWED_IMAGE_EXTENSIONS) or \
                   not allowed_file(new_annotation_file.filename, Config.ALLOWED_ANNOTATION_EXTENSIONS):
                    flash('Неверный формат файла')
                    return render_template('teacher/edit_question.html', question=question, topics=topics)

                try:
                    # Удаление старого файла если он был и не используется в других вопросах
                    if question.image_annotation:
                        old_annotation = question.image_annotation
                        # Проверяем, используется ли аннотация в других вопросах
                        other_questions_using_this_annotation = Question.query.filter_by(image_annotation_id=old_annotation.id).filter(Question.id != question.id).count()
                        if other_questions_using_this_annotation == 0:
                            # Удаляем файлы изображения и аннотации
                            try:
                                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], 'images', old_annotation.image_file))
                                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], 'annotations', old_annotation.annotation_file))
                            except FileNotFoundError:
                                print('FileNotFoundError')
                                pass # Файлы уже удалены или не существуют
                            # Удаляем запись из БД
                            db.session.delete(old_annotation)

                    # Сохранение новых файлов (аналогично create_question)
                    image_filename = secure_filename(new_image_file.filename)
                    annotation_filename = secure_filename(new_annotation_file.filename)

                    import uuid
                    unique_id = str(uuid.uuid4())[:8]
                    name_part_img, ext_part_img = os.path.splitext(image_filename)
                    name_part_ann, ext_part_ann = os.path.splitext(annotation_filename)
                    image_filename = f"{name_part_img}_{unique_id}{ext_part_img}"
                    annotation_filename = f"{name_part_ann}_{unique_id}{ext_part_ann}"

                    image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'images', image_filename)
                    annotation_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'annotations', annotation_filename)

                    os.makedirs(os.path.dirname(image_path), exist_ok=True)
                    os.makedirs(os.path.dirname(annotation_path), exist_ok=True)

                    new_image_file.save(image_path)
                    new_annotation_file.save(annotation_path)

                    format_type = 'coco' if annotation_filename.endswith('.json') else 'yolo'

                    if format_type == 'coco':
                        processed_data = process_coco_annotations(annotation_path)
                    else:
                        img = cv2.imread(image_path)
                        if img is None:
                            flash('Не удалось загрузить изображение для обработки YOLO')
                            return render_template('teacher/edit_question.html', question=question, topics=topics)
                        processed_data = process_yolo_annotations(annotation_path, img.shape)

                    if processed_data is None:
                        flash('Не удалось обработать файл аннотации')
                        return render_template('teacher/edit_question.html', question=question, topics=topics)

                    new_annotation = ImageAnnotation(
                        image_file=image_filename,
                        annotation_file=annotation_filename,
                        format_type=format_type,
                        labels=json.dumps(processed_data['labels'])
                    )

                    db.session.add(new_annotation)
                    db.session.flush()

                    question.image_annotation_id = new_annotation.id
                    # Если нужно хранить ID в correct_answer:
                    # question.correct_answer = str(new_annotation.id)

                except Exception as e:
                    db.session.rollback()
                    flash(f'Ошибка при обновлении файлов: {str(e)}')
                    return render_template('teacher/edit_question.html', question=question, topics=topics)

        db.session.commit()
        flash('Вопрос успешно обновлен')
        return redirect(url_for('teacher.view_questions'))

    return render_template('teacher/edit_question.html', question=question, topics=topics)

@bp.route('/teacher/delete_question/<int:question_id>')
@login_required
def delete_question(question_id):
    """
    Удаление вопроса с каскадным удалением аннотации и файлов

    Только владелец вопроса или админ могут удалить.
    Аннотация удаляется только если не используется другими вопросами.
    Файлы удаляются только при удалении аннотации.
    """
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    question = Question.query.get_or_404(question_id)

    # Проверка прав доступа
    if question.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.view_questions'))

    try:
        annotation = question.image_annotation
        annotation_deleted = False

        # Удаляем аннотацию (и файлы), только если она существует и не используется другими вопросами
        if annotation:
            # Проверяем, используется ли аннотация другими вопросами
            other_count = Question.query.filter(
                Question.image_annotation_id == annotation.id,
                Question.id != question.id
            ).count()

            if other_count == 0:
                # Удаляем файлы
                upload_folder = current_app.config['UPLOAD_FOLDER']
                image_path = os.path.join(upload_folder, 'images', annotation.image_file)
                annotation_path = os.path.join(upload_folder, 'annotations', annotation.annotation_file)

                # Удаляем файлы (игнорируем, если не найдены)
                for path in [image_path, annotation_path]:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except OSError as e:
                        pass

                # Удаляем запись аннотации из БД
                db.session.delete(annotation)
                annotation_deleted = True

        # Удаляем вопрос
        db.session.delete(question)
        db.session.commit()

        if annotation_deleted:
            flash(_('Вопрос и связанные файлы успешно удалены'))
        else:
            flash(_('Вопрос удалён'))

    except Exception as e:
        db.session.rollback()
        #import traceback
        #traceback.print_exc()
        flash(_('Ошибка при удалении вопроса. Обратитесь к администратору.'))

    # Возврат с сохранением параметров (пагинация, сортировка)
    next_url = request.args.get('next')
    if next_url and is_safe_url(next_url):  # ← убедитесь, что is_safe_url импортирован
        return redirect(next_url)
    return redirect(url_for('teacher.view_questions'))

@bp.route('/teacher/view_questions')
@login_required
def view_questions():
    """
    Маршрут для просмотра созданных тестов
    """
    # Получаем параметры сортировки из запроса
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')

    topics = TestTopic.query.all()
    topic_map = {topic.id: topic.name for topic in topics}  # ← остаётся в памяти как dict

    if current_user.role not in ['admin', 'teacher']:
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
        query = Question.query.filter_by(creator_id=current_user.id).join(TestTopic, Question.topic_id == TestTopic.id).order_by(sort_expr)

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

    return render_template('teacher/view_questions.html',
                          questions=questions,
                          topic_map=topic_map,
                          pagination=pagination,
                          current_per_page=per_page_raw)

@bp.route('/teacher/view_results')
@login_required
def view_results():
    """
    Маршрут для просмотра результатов тестов
    """
    if current_user.role not in ['admin', 'teacher']:
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Преподаватель видит результаты по своим тестам, администратор - все
    if current_user.role == 'admin':
        results = TestResult.query.all()
    else:
        # Получаем ID тестов, созданных текущим преподавателем
        teacher_test_ids = Test.query.filter_by(creator_id=current_user.id).with_entities(Test.id).all()
        test_ids = [test_id for test_id, in teacher_test_ids] if teacher_test_ids else []
        results = TestResult.query.filter(TestResult.test_id.in_(test_ids)).all()

    return render_template('teacher/view_results.html', results=results)

@bp.route('/teacher/generate_variant', methods=['GET', 'POST'])
@login_required
def generate_variant():
    """
    Маршрут для генерации варианта задания для студентов

    GET: Отображает форму выбора параметров
    POST: Генерирует и отображает/сохраняет вариант
    """
    if current_user.role not in ['admin', 'teacher']:
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        topic_id = request.form.get('topic_id')
        num_questions = int(request.form.get('num_questions', 10))  # По умолчанию 10 вопросов
        difficulty = request.form.get('difficulty', 'medium')  # По умолчанию средняя сложность (не реализовано)

        # Получаем тесты по выбранной теме
        if topic_id:
            tests = Test.query.filter_by(topic_id=topic_id).all()
        else:
            tests = Test.query.all()

        # Собираем все вопросы из выбранных тестов
        all_questions = []
        for test in tests:
            all_questions.extend(test.questions)

        # Выбираем случайные вопросы
        import random
        selected_questions = random.sample(all_questions, min(len(all_questions), num_questions))

        # В реальном приложении, здесь можно было бы создать новый "тест-вариант" и сохранить его
        # или сгенерировать PDF/HTML файл с заданием
        # Для демонстрации, просто отобразим выбранные вопросы
        return render_template('teacher/generated_variant.html', questions=selected_questions)

    topics = TestTopic.query.all()
    return render_template('teacher/generate_variant.html', topics=topics)


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