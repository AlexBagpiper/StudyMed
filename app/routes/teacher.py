# app/routes/teacher.py (новый файл)
"""
Маршруты преподавателя приложения медицинского тестирования
Содержит логику управления тестами, просмотра результатов и конструктора
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test import TestTopic
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

    return render_template('teacher/index.html', tests=tests)

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

                image_path = os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'images', image_filename)
                annotation_path = os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'annotations', annotation_filename)

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
                    filename=image_filename,
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
                                os.remove(os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'images', old_annotation.filename))
                                os.remove(os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'annotations', old_annotation.annotation_file))
                            except FileNotFoundError:
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

                    image_path = os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'images', image_filename)
                    annotation_path = os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'annotations', annotation_filename)

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
                        filename=image_filename,
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
    Маршрут для удаления вопроса
    Только для преподавателей и администраторов
    """
    if current_user.role not in ['admin', 'teacher']:
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    question = Question.query.get_or_404(question_id)

    # Проверка прав доступа
    if question.creator_id != current_user.id and current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('teacher.view_questions'))

    # Удаление файла изображения/аннотации если он не используется другими вопросами
    if question.image_annotation:
        annotation_to_delete = question.image_annotation
        other_questions_using_this_annotation = Question.query.filter_by(image_annotation_id=annotation_to_delete.id).filter(Question.id != question.id).count()
        if other_questions_using_this_annotation == 0:
            try:
                os.remove(os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'images', annotation_to_delete.filename))
                os.remove(os.path.join(current_user.app.config['UPLOAD_FOLDER'], 'annotations', annotation_to_delete.annotation_file))
            except FileNotFoundError:
                pass # Файлы уже удалены или не существуют
            db.session.delete(annotation_to_delete)

    db.session.delete(question)
    db.session.commit()

    flash('Вопрос успешно удален')
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

    # Определяем поля сортировки
    sort_fields = {
        'user': Question.creator_id,
        'topic': TestTopic.name,
        'type': Question.question_type,
        'date': Question.created_at
    }

    # Получаем поле для сортировки
    sort_field = sort_fields.get(sort_by, Question.created_at)

    # Определяем направление сортировки
    if order == 'asc':
        sort_expr = asc(sort_field)
    else:
        sort_expr = desc(sort_field)

    # Преподаватель видит только свои тесты, администратор - все
    if current_user.role == 'admin':
        query = Question.query.join(TestTopic, Question.topic_id == TestTopic.id).order_by(sort_expr)
    else:
        query = Question.query.filter_by(creator_id=current_user.id).join(TestTopic, Question.topic_id == TestTopic.id).order_by(sort_expr)

    # Пагинация
    page = request.args.get('page', 1, type=int)
    per_page = 10  # количество вопросов на странице
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    questions = pagination.items

    return render_template('teacher/view_questions.html',
                          questions=questions,
                          topic_map=topic_map,
                          pagination=pagination)

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

@bp.route('/teacher/add_question/<int:test_id>', methods=['POST'])
@login_required
def add_question(test_id):
    """
    Маршрут для добавления вопроса к тесту

    Args:
        test_id (int): ID теста
    """
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    test = Test.query.get_or_404(test_id)
    if test.creator_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    question_type = request.form['question_type']
    question_text = request.form['question_text']
    correct_answer = request.form['correct_answer']  # Для графических - ID аннотации, для текстовых - текст

    new_question = Question(
        test_id=test_id,
        question_text=question_text,
        question_type=question_type,
        correct_answer=correct_answer
    )
    db.session.add(new_question)
    db.session.commit()

    flash('Вопрос добавлен успешно')
    return redirect(url_for('teacher.edit_test', test_id=test_id))

@bp.route('/teacher/delete_test/<int:test_id>')
@login_required
def delete_test(test_id):
    """
    Маршрут для удаления теста

    Args:
        test_id (int): ID теста
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('teacher.index'))

    test = Test.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()

    flash('Тест удален успешно')
    return redirect(url_for('teacher.view_tests'))

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