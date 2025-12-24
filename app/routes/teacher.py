"""
Маршруты преподавателя приложения медицинского тестирования
Содержит логику управления тестами, просмотра результатов и конструктора
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.test_topics import TestTopic
from app.models.question import Question
from app.models.annotation import ImageAnnotation, TestResult
from app.models.test_variant import Test, Variant
from werkzeug.utils import secure_filename
import os
import uuid
import json
import random
from app.utils.image_processing import parse_coco_for_image
from sqlalchemy import asc, desc, func
from urllib.parse import urlparse, urljoin
from flask_babel import _


bp = Blueprint('teacher', __name__)


# === Вспомогательные функции ===

def allowed_file(filename, extensions_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions_set


def is_safe_url(target):
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


def generate_variants_batch_impl(test, count, user_role, user_id):
    """
    Генерирует `count` вариантов для теста.
    Возвращает: (список Variant, список ошибок)
    """
    if count < 1 or count > 50:
        return [], [_('Количество должно быть от 1 до 50')]

    try:
        structure = json.loads(test.structure) if test.structure else []
    except (ValueError, TypeError, json.JSONDecodeError):
        return [], [_('Некорректная структура теста')]

    if not structure:
        return [], [_('Структура теста пуста')]

    new_variants = []
    errors = []

    for i in range(count):
        question_id_list = []
        for item in structure:
            topic_id = item.get('topic_id')
            q_type = item.get('question_type')

            if not topic_id or not q_type:
                errors.append(_('Ошибка в структуре: пустой элемент'))
                continue

            query = Question.query.filter_by(topic_id=topic_id, question_type=q_type)
            if user_role != 'admin':
                query = query.filter(Question.creator_id == user_id)

            available = query.all()
            if not available:
                errors.append(
                    _('Нет вопросов для: тема %(topic)s, тип %(type)s (вариант %(num)d)',
                      topic=topic_id, type=q_type, num=i + 1)
                )
                break

            chosen = random.choice(available)
            question_id_list.append(chosen.id)
        else:
            new_variant = Variant(
                test_id=test.id,
                question_id_list=json.dumps(question_id_list, ensure_ascii=False)
            )
            new_variants.append(new_variant)
            continue
        break

    return new_variants, errors


# === Роуты ===

@bp.route('/teacher')
@login_required
def index():
    return render_template('teacher/index.html')


@bp.route('/teacher/create_question', methods=['GET', 'POST'])
@login_required
def create_question():
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    topics = TestTopic.query.all()

    if request.method == 'POST':
        question_text = request.form['question_text']
        question_type = request.form['question_type']
        topic_id = request.form['topic_id']

        new_question = Question(
            question_text=question_text,
            question_type=question_type,
            topic_id=topic_id,
            creator_id=current_user.id
        )

        if question_type == 'graphic':
            image_file = request.files.get('image_file')
            annotation_file = request.files.get('annotation_file')

            if not image_file or not annotation_file:
                flash(_('Для графических вопросов требуются файлы изображения и аннотации'))
                return render_template('teacher/create_question.html', topics=topics)

            allowed_image_ext = set(current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg'}))
            allowed_ann_ext = set(current_app.config.get('ALLOWED_ANNOTATION_EXTENSIONS', {'json'}))

            if not allowed_file(image_file.filename, allowed_image_ext) or \
               not allowed_file(annotation_file.filename, allowed_ann_ext):
                flash(_('Неверный формат файла'))
                return render_template('teacher/create_question.html', topics=topics)

            try:
                image_filename = secure_filename(image_file.filename)
                annotation_filename = secure_filename(annotation_file.filename)

                unique_id = str(uuid.uuid4())[:8]
                name_part_img, ext_part_img = os.path.splitext(image_filename)
                name_part_ann, ext_part_ann = os.path.splitext(annotation_filename)

                raw_image_filename = f"{name_part_img}{ext_part_img}"
                image_filename = f"{name_part_img}_{unique_id}{ext_part_img}"
                annotation_filename = f"{name_part_ann}_{unique_id}{ext_part_ann}"

                upload_folder = current_app.config.get('UPLOAD_FOLDER')
                if not upload_folder:
                    raise RuntimeError("UPLOAD_FOLDER not configured")

                image_path = os.path.join(upload_folder, 'images', image_filename)
                annotation_path = os.path.join(upload_folder, 'annotations', annotation_filename)

                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                os.makedirs(os.path.dirname(annotation_path), exist_ok=True)

                image_file.save(image_path)
                annotation_file.save(annotation_path)

                format_type = 'coco' if annotation_filename.endswith('.json') else 'yolo'

                if format_type == 'coco':
                    success, result = parse_coco_for_image(annotation_path, raw_image_filename, unique_id)
                    if not success:
                        flash(result)
                        try:
                            os.remove(image_path)
                        except OSError:
                            pass
                        return render_template('teacher/create_question.html', topics=topics)
                    else:
                        os.remove(annotation_path)
                        annotation_filename = result

                new_annotation = ImageAnnotation(
                    image_file=image_filename,
                    annotation_file=annotation_filename,
                    format_type=format_type
                )

                db.session.add(new_annotation)
                db.session.flush()
                new_question.image_annotation_id = new_annotation.id

            except Exception as e:
                db.session.rollback()
                current_app.logger.exception("Error in create_question (graphic)")
                flash(_('Ошибка при загрузке файлов: %(error)s', error=str(e)))
                return render_template('teacher/create_question.html', topics=topics)

        elif question_type == 'open':
            correct_answer = request.form.get('correct_answer', '').strip()
            new_question.correct_answer = correct_answer

        db.session.add(new_question)
        db.session.commit()
        flash(_('Вопрос успешно создан'))
        return redirect(url_for('teacher.view_questions'))

    return render_template('teacher/create_question.html', topics=topics)


@bp.route('/teacher/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    question = Question.query.get_or_404(question_id)
    topics = TestTopic.query.all()

    if question.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.view_questions'))

    if request.method == 'POST':
        question.topic_id = request.form['topic_id']
        question.question_text = request.form['question_text']
        question.question_type = request.form['question_type']

        if question.question_type == 'open':
            question.correct_answer = request.form.get('correct_answer', '').strip()
            question.image_annotation_id = None

        elif question.question_type == 'graphic':
            new_image_file = request.files.get('image_file')
            new_annotation_file = request.files.get('annotation_file')

            if new_image_file and new_annotation_file:
                allowed_image_ext = set(current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg'}))
                allowed_ann_ext = set(current_app.config.get('ALLOWED_ANNOTATION_EXTENSIONS', {'json'}))

                if not allowed_file(new_image_file.filename, allowed_image_ext) or \
                   not allowed_file(new_annotation_file.filename, allowed_ann_ext):
                    flash(_('Неверный формат файла'))
                    return render_template('teacher/edit_question.html', question=question, topics=topics)

                try:
                    if question.image_annotation:
                        old_annotation = question.image_annotation
                        other_count = Question.query.filter(
                            Question.image_annotation_id == old_annotation.id,
                            Question.id != question_id
                        ).count()

                        if other_count == 0:
                            upload_folder = current_app.config.get('UPLOAD_FOLDER')
                            if upload_folder:
                                img_path = os.path.join(upload_folder, 'images', old_annotation.image_file)
                                ann_path = os.path.join(upload_folder, 'annotations', old_annotation.annotation_file)
                                for p in [img_path, ann_path]:
                                    if os.path.exists(p):
                                        try:
                                            os.remove(p)
                                        except OSError as e:
                                            current_app.logger.warning(f"Failed to remove {p}: {e}")
                            db.session.delete(old_annotation)

                    image_filename = secure_filename(new_image_file.filename)
                    annotation_filename = secure_filename(new_annotation_file.filename)

                    unique_id = str(uuid.uuid4())[:8]
                    name_part_img, ext_part_img = os.path.splitext(image_filename)
                    name_part_ann, ext_part_ann = os.path.splitext(annotation_filename)

                    raw_image_filename = f"{name_part_img}{ext_part_img}"
                    image_filename = f"{name_part_img}_{unique_id}{ext_part_img}"
                    annotation_filename = f"{name_part_ann}_{unique_id}{ext_part_ann}"

                    upload_folder = current_app.config.get('UPLOAD_FOLDER')
                    if not upload_folder:
                        raise RuntimeError("UPLOAD_FOLDER not configured")

                    image_path = os.path.join(upload_folder, 'images', image_filename)
                    annotation_path = os.path.join(upload_folder, 'annotations', annotation_filename)

                    os.makedirs(os.path.dirname(image_path), exist_ok=True)
                    os.makedirs(os.path.dirname(annotation_path), exist_ok=True)

                    new_image_file.save(image_path)
                    new_annotation_file.save(annotation_path)

                    format_type = 'coco' if annotation_filename.endswith('.json') else 'yolo'

                    if format_type == 'coco':
                        success, result = parse_coco_for_image(annotation_path, raw_image_filename, unique_id)
                        if not success:
                            flash(result)
                            try:
                                os.remove(image_path)
                            except OSError:
                                pass
                            return render_template('teacher/edit_question.html', question=question, topics=topics)
                        os.remove(annotation_path)
                        annotation_filename = result

                    new_annotation = ImageAnnotation(
                        image_file=image_filename,
                        annotation_file=annotation_filename,
                        format_type=format_type
                    )

                    db.session.add(new_annotation)
                    db.session.flush()
                    question.image_annotation_id = new_annotation.id

                except Exception as e:
                    db.session.rollback()
                    current_app.logger.exception("Error in edit_question (graphic)")
                    flash(_('Ошибка при обновлении файлов: %(error)s', error=str(e)))
                    return render_template('teacher/edit_question.html', question=question, topics=topics)

        db.session.commit()
        flash(_('Вопрос успешно обновлён'))
        return redirect(url_for('teacher.view_questions'))

    return render_template('teacher/edit_question.html', question=question, topics=topics)


@bp.route('/teacher/delete_question/<int:question_id>')
@login_required
def delete_question(question_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    question = Question.query.get_or_404(question_id)

    if question.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.view_questions'))

    try:
        annotation = question.image_annotation
        annotation_deleted = False

        if annotation:
            other_count = Question.query.filter(
                Question.image_annotation_id == annotation.id,
                Question.id != question_id
            ).count()

            if other_count == 0:
                upload_folder = current_app.config.get('UPLOAD_FOLDER')
                if upload_folder:
                    img_path = os.path.join(upload_folder, 'images', annotation.image_file)
                    ann_path = os.path.join(upload_folder, 'annotations', annotation.annotation_file)
                    for p in [img_path, ann_path]:
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except OSError as e:
                                current_app.logger.warning(f"Failed to delete {p}: {e}")
                db.session.delete(annotation)
                annotation_deleted = True

        db.session.delete(question)
        db.session.commit()

        if annotation_deleted:
            flash(_('Вопрос и связанные файлы успешно удалены'))
        else:
            flash(_('Вопрос удалён'))

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error in delete_question")
        flash(_('Ошибка при удалении вопроса. Обратитесь к администратору.'))

    next_url = request.args.get('next')
    if next_url and is_safe_url(next_url):
        return redirect(next_url)
    return redirect(url_for('teacher.view_questions'))


@bp.route('/teacher/view_questions')
@login_required
def view_questions():
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    per_page_raw = request.args.get('per_page', '10')

    topics = TestTopic.query.all()
    topic_map = {t.id: t.name for t in topics}

    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    sort_fields = {
        'user': Question.creator_id,
        'topic': TestTopic.name,
        'type': Question.question_type,
        'date': Question.created_at
    }

    sort_field = sort_fields.get(sort_by, Question.created_at)
    sort_expr = asc(sort_field) if order == 'asc' else desc(sort_field)

    base_query = Question.query.join(TestTopic, Question.topic_id == TestTopic.id).order_by(sort_expr)
    if current_user.role != 'admin':
        base_query = base_query.filter(Question.creator_id == current_user.id)

    page = request.args.get('page', 1, type=int)

    if per_page is None:
        questions = base_query.all()
        pagination = None
    else:
        pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
        questions = pagination.items

    return render_template('teacher/view_questions.html',
                          questions=questions,
                          topic_map=topic_map,
                          pagination=pagination,
                          current_per_page=per_page_raw)


@bp.route('/teacher/view_results')
@login_required
def view_results():
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    if current_user.role == 'admin':
        results = TestResult.query.all()
    else:
        results = []

    return render_template('teacher/view_results.html', results=results)


# ==================== КОНСТРУКТОР ТЕСТОВ ====================

@bp.route('/teacher/test_constructor', methods=['GET', 'POST'])
@login_required
def test_constructor():
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('main.index'))

    topics = TestTopic.query.order_by(TestTopic.name).all()
    topic_choices = [{'id': t.id, 'name': t.name} for t in topics]
    question_types = [
        {'value': 'open', 'label': _('Открытый')},
        {'value': 'graphic', 'label': _('Графический')}
    ]

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        structure_raw = request.form.get('structure', '[]')

        if not name:
            flash(_('Название теста обязательно'))
            return render_template('teacher/test_constructor.html',
                                   topics=topics,
                                   topic_choices=topic_choices,
                                   question_types=question_types,
                                   name=name,
                                   description=description,
                                   structure_raw=structure_raw)

        try:
            structure = json.loads(structure_raw)
            if not isinstance(structure, list):
                raise ValueError
            for item in structure:
                if not isinstance(item, dict):
                    raise ValueError
                if 'topic_id' not in item or 'question_type' not in item:
                    raise ValueError
                if item['topic_id'] not in [t.id for t in topics]:
                    raise ValueError
                if item['question_type'] not in ['open', 'graphic']:
                    raise ValueError
        except (ValueError, TypeError, json.JSONDecodeError):
            flash(_('Некорректная структура теста'))
            return render_template('teacher/test_constructor.html',
                                   topics=topics,
                                   topic_choices=topic_choices,
                                   question_types=question_types,
                                   name=name,
                                   description=description,
                                   structure_raw=structure_raw)

        new_test = Test(
            name=name,
            description=description,
            structure=json.dumps(structure, ensure_ascii=False),
            creator_id=current_user.id
        )

        try:
            db.session.add(new_test)
            db.session.commit()
            flash(_('Тест успешно создан'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Ошибка создания теста")
            flash(_('Ошибка при создании теста. Обратитесь к администратору.'))
        return redirect(url_for('teacher.test_constructor'))

    # GET: пагинация списка тестов
    base_query = Test.query
    if current_user.role != 'admin':
        base_query = base_query.filter(Test.creator_id == current_user.id)
    base_query = base_query.order_by(Test.created_at.desc())

    per_page_raw = request.args.get('per_page', '10')
    try:
        per_page = int(per_page_raw) if per_page_raw != 'all' else None
    except (TypeError, ValueError):
        per_page = 10

    page = request.args.get('page', 1, type=int)

    if per_page is None:
        tests = base_query.all()
        pagination = None
    else:
        pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
        tests = pagination.items

    topic_map = {t.id: t.name for t in topics}

    return render_template('teacher/test_constructor.html',
                           tests=tests,
                           pagination=pagination,
                           topic_map=topic_map,
                           topics=topics,
                           topic_choices=topic_choices,
                           question_types=question_types,
                           name='',
                           description='',
                           structure_raw='[]')


@bp.route('/teacher/test_constructor/delete/<int:test_id>', methods=['POST'])
@login_required
def delete_test(test_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    test = Test.query.get_or_404(test_id)

    if test.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    try:
        db.session.delete(test)
        db.session.commit()
        flash(_('Тест и все его варианты успешно удалены'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Ошибка удаления теста")
        flash(_('Ошибка при удалении теста'))

    next_url = request.args.get('next')
    if next_url and is_safe_url(next_url):
        return redirect(next_url)
    return redirect(url_for('teacher.test_constructor'))


@bp.route('/teacher/test_constructor/view/<int:test_id>')
@login_required
def view_test(test_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    test = Test.query.get_or_404(test_id)

    if test.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    topics = TestTopic.query.all()
    topic_map = {t.id: t.name for t in topics}

    try:
        structure = json.loads(test.structure) if test.structure else []
    except (ValueError, TypeError):
        structure = []

    questions_by_item = []
    for idx, item in enumerate(structure):
        topic_id = item.get('topic_id')
        q_type = item.get('question_type')
        examples = Question.query.filter_by(
            topic_id=topic_id,
            question_type=q_type
        ).limit(3).all()
        questions_by_item.append({
            'index': idx + 1,
            'topic_id': topic_id,
            'topic_name': topic_map.get(topic_id, '?'),
            'question_type': q_type,
            'type_label': _('Открытый') if q_type == 'open' else _('Графический'),
            'examples': examples
        })

    stats_rows = db.session.query(
        Question.topic_id,
        Question.question_type,
        func.count(Question.id).label('count')
    ).filter(Question.topic_id.isnot(None))

    if current_user.role != 'admin':
        stats_rows = stats_rows.filter(Question.creator_id == current_user.id)

    stats_rows = stats_rows.group_by(Question.topic_id, Question.question_type).all()

    stats = {}
    for tid, qtype, cnt in stats_rows:
        stats[f"{tid},{qtype}"] = cnt

    all_topics = [t.id for t in topics]
    all_types = ['open', 'graphic']
    for tid in all_topics:
        for qtype in all_types:
            key = f"{tid},{qtype}"
            if key not in stats:
                stats[key] = 0

    total_open = sum(cnt for key, cnt in stats.items() if key.endswith(',open'))
    total_graphic = sum(cnt for key, cnt in stats.items() if key.endswith(',graphic'))

    return render_template('teacher/view_test.html',
                           test=test,
                           structure=structure,
                           questions_by_item=questions_by_item,
                           stats=stats,
                           total_open=total_open,
                           total_graphic=total_graphic,
                           total_questions=total_open + total_graphic,
                           topic_map=topic_map)


@bp.route('/teacher/test_constructor/stats')
@login_required
def stats_api():
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'forbidden'}), 403

    stats_rows = db.session.query(
        Question.topic_id,
        Question.question_type,
        func.count(Question.id).label('count')
    ).filter(Question.topic_id.isnot(None))

    if current_user.role != 'admin':
        stats_rows = stats_rows.filter(Question.creator_id == current_user.id)

    stats_rows = stats_rows.group_by(Question.topic_id, Question.question_type).all()

    stats = {}
    for tid, qtype, cnt in stats_rows:
        stats[f"{tid},{qtype}"] = cnt

    all_topics = [t.id for t in TestTopic.query.all()]
    all_types = ['open', 'graphic']
    for tid in all_topics:
        for qtype in all_types:
            key = f"{tid},{qtype}"
            stats[key] = stats.get(key, 0)

    return jsonify(stats)


@bp.route('/teacher/test_constructor/generate/<int:test_id>', methods=['POST'])
@login_required
def generate_variant(test_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    test = Test.query.get_or_404(test_id)

    if test.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.view_test', test_id=test.id))

    new_variants, errors = generate_variants_batch_impl(
        test, 1,
        user_role=current_user.role,
        user_id=current_user.id
    )

    if errors:
        for err in errors:
            flash(err)
        return redirect(url_for('teacher.view_test', test_id=test.id))

    try:
        db.session.add(new_variants[0])
        db.session.commit()
        flash(_('Вариант успешно сгенерирован'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Ошибка генерации варианта")
        flash(_('Ошибка при создании варианта'))

    next_url = request.args.get('next')
    if next_url and is_safe_url(next_url):
        return redirect(next_url)
    return redirect(url_for('teacher.view_test', test_id=test.id))


@bp.route('/teacher/test_constructor/edit/<int:test_id>', methods=['GET', 'POST'])
@login_required
def edit_test(test_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    test = Test.query.get_or_404(test_id)

    if test.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    topics = TestTopic.query.order_by(TestTopic.name).all()
    topic_choices = [{'id': t.id, 'name': t.name} for t in topics]
    question_types = [
        {'value': 'open', 'label': _('Открытый')},
        {'value': 'graphic', 'label': _('Графический')}
    ]

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        structure_raw = request.form.get('structure', '[]')

        if not name:
            flash(_('Название теста обязательно'))
            return render_template('teacher/edit_test.html',
                                   test=test,
                                   topics=topics,
                                   topic_choices=topic_choices,
                                   question_types=question_types,
                                   name=name,
                                   description=description,
                                   structure_raw=structure_raw)

        try:
            structure = json.loads(structure_raw)
            if not isinstance(structure, list):
                raise ValueError
            for item in structure:
                if not isinstance(item, dict) or \
                   'topic_id' not in item or 'question_type' not in item:
                    raise ValueError
                if item['topic_id'] not in [t.id for t in topics]:
                    raise ValueError
                if item['question_type'] not in ['open', 'graphic']:
                    raise ValueError
        except (ValueError, TypeError, json.JSONDecodeError):
            flash(_('Некорректная структура теста'))
            return render_template('teacher/edit_test.html',
                                   test=test,
                                   topics=topics,
                                   topic_choices=topic_choices,
                                   question_types=question_types,
                                   name=name,
                                   description=description,
                                   structure_raw=structure_raw)

        test.name = name
        test.description = description
        test.structure = json.dumps(structure, ensure_ascii=False)

        try:
            db.session.commit()
            flash(_('Тест успешно обновлён'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Ошибка обновления теста")
            flash(_('Ошибка при сохранении теста'))
        next_url = request.args.get('next')
        if next_url and is_safe_url(next_url):
            return redirect(next_url)
        return redirect(url_for('teacher.view_test', test_id=test.id))

    try:
        structure = json.loads(test.structure) if test.structure else []
    except:
        structure = []

    return render_template('teacher/edit_test.html',
                           test=test,
                           topics=topics,
                           topic_choices=topic_choices,
                           question_types=question_types,
                           name=test.name,
                           description=test.description,
                           structure_raw=json.dumps(structure, ensure_ascii=False))


@bp.route('/teacher/test_constructor/variant/<int:variant_id>')
@login_required
def view_variant(variant_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    variant = Variant.query.get_or_404(variant_id)
    test = variant.test

    topics = TestTopic.query.all()
    topic_map = {t.id: t.name for t in topics}

    if test.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.view_test', test_id=test.id))

    try:
        question_ids = json.loads(variant.question_id_list) if variant.question_id_list else []
    except:
        question_ids = []

    questions = []
    for qid in question_ids:
        q = Question.query.get(qid)
        if q:
            questions.append(q)

    return render_template('teacher/view_variant.html',
                           variant=variant,
                           test=test,
                           questions=questions,
                           topic_map=topic_map)


@bp.route('/teacher/test_constructor/batch/<int:test_id>', methods=['POST'])
@login_required
def generate_variants_batch(test_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    test = Test.query.get_or_404(test_id)

    if test.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.view_test', test_id=test.id))

    try:
        count = int(request.form.get('count', 1))
    except (TypeError, ValueError):
        flash(_('Некорректное количество'))
        return redirect(url_for('teacher.view_test', test_id=test.id))

    new_variants, errors = generate_variants_batch_impl(
        test, count,
        user_role=current_user.role,
        user_id=current_user.id
    )

    if errors:
        for err in errors[:3]:
            flash(err)
        if len(errors) > 3:
            flash(_('... и ещё %(n)d ошибок', n=len(errors) - 3))
    else:
        try:
            db.session.add_all(new_variants)
            db.session.commit()
            flash(_('Успешно создано %(count)d вариантов', count=len(new_variants)))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Ошибка пакетной генерации")
            flash(_('Ошибка при сохранении вариантов'))

    next_url = request.args.get('next')
    if next_url and is_safe_url(next_url):
        return redirect(next_url)
    return redirect(url_for('teacher.view_test', test_id=test.id))


# ==================== УДАЛЕНИЕ ВАРИАНТА ====================
@bp.route('/teacher/test_constructor/variant/delete/<int:variant_id>', methods=['POST'])
@login_required
def delete_variant(variant_id):
    if current_user.role not in ['admin', 'teacher']:
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.test_constructor'))

    variant = Variant.query.get_or_404(variant_id)
    test = variant.test

    if test.creator_id != current_user.id and current_user.role != 'admin':
        flash(_('Доступ запрещён'))
        return redirect(url_for('teacher.view_test', test_id=test.id))

    # Защита: подтверждение по ID варианта (опционально — можно добавить modal как для теста)
    try:
        db.session.delete(variant)
        db.session.commit()
        flash(_('Вариант успешно удалён'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Ошибка удаления варианта")
        flash(_('Ошибка при удалении варианта'))

    next_url = request.args.get('next')
    if next_url and is_safe_url(next_url):
        return redirect(next_url)
    return redirect(url_for('teacher.view_test', test_id=test.id))