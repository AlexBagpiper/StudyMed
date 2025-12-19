# app/routes/student.py (обновленный)
"""
Маршруты студента приложения медицинского тестирования
Содержит логику прохождения тестов и просмотра результатов
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models.question import Question
from app.models.annotation import ImageAnnotation, TestResult
from app.models.user import User
from app.utils.contour_metrics import evaluate_graphic_answer_with_metrics, calculate_comprehensive_contour_score
from config import Config
from datetime import datetime
import json

# Создание Blueprint для маршрутов студента
bp = Blueprint('student', __name__)

@bp.route('/tests')
@login_required
def view_tests():
    """
    Главная страница тестирования для студента - отображает меню
    """
    if current_user.role != 'student':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    return render_template('student/tests_dashboard.html')

@bp.route('/tests/list')
@login_required
def list_tests():
    """
    Маршрут для просмотра списка доступных тестов
    """
    if current_user.role != 'student':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    tests = Test.query.all()

    # Рассчитываем прогресс для каждого теста
    for test in tests:
        total_questions = len(test.questions)
        if total_questions > 0:
            # Получаем последний результат для этого теста и текущего пользователя
            latest_result = TestResult.query.filter_by(user_id=current_user.id, test_id=test.id).order_by(TestResult.completed_at.desc()).first()
            if latest_result:
                # Используем сохраненные ответы для подсчета прогресса (если они хранятся как список вопросов)
                # В реальности это может быть сложнее, зависит от структуры TestResult
                # Пока используем простой расчет на основе существования результата
                test.progress = 100  # или рассчитываем на основе ответов
            else:
                test.progress = 0
        else:
            test.progress = 0

    return render_template('student/tests_list.html', tests=tests)

@bp.route('/test/<int:test_id>/start')
@login_required
def start_test(test_id):
    """
    Маршрут для начала прохождения теста
    """
    if current_user.role != 'student':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()

    # Разделение вопросов по типам
    graphic_questions = [q for q in questions if q.question_type == 'graphic']
    text_questions = [q for q in questions if q.question_type == 'text'] # или 'open'

    # Добавление аннотаций к графическим вопросам
    for question in graphic_questions:
        try:
            annotation_id = int(question.correct_answer)
            question.annotation = ImageAnnotation.query.get(annotation_id)
        except (ValueError, TypeError):
            question.annotation = None

    return render_template('student/take_test.html', test=test, graphic_questions=graphic_questions, text_questions=text_questions)

@bp.route('/submit_test/<int:test_id>', methods=['POST'])
@login_required
def submit_test(test_id):
    """
    Маршрут для отправки результатов теста
    """
    if current_user.role != 'student':
        return jsonify({'error': 'Доступ запрещен'}), 403

    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()

    score = 0
    total_questions = len(questions)
    answers = {}
    metrics = {}

    started_at = datetime.utcnow()

    for question in questions:
        if question.question_type == 'text': # или 'open'
            user_answer = request.form.get(f'text_{question.id}')
            answers[f'text_{question.id}'] = user_answer

            # Проверка текстового ответа
            if user_answer and question.correct_answer:
                if user_answer.lower().strip() == question.correct_answer.lower().strip():
                    score += 1
                    metrics[f'text_{question.id}'] = {'correct': True, 'match_type': 'exact'}
                else:
                    # Можно реализовать частичный балл для текстовых вопросов
                    correct_answer = question.correct_answer.lower().strip()
                    user_answer_clean = user_answer.lower().strip()
                    common_chars = sum(1 for c in user_answer_clean if c in correct_answer)
                    similarity = common_chars / len(correct_answer) if len(correct_answer) > 0 else 0
                    partial_score = min(similarity, 0.5)
                    score += partial_score
                    metrics[f'text_{question.id}'] = {'correct': False, 'match_type': 'partial', 'partial_score': partial_score, 'similarity': similarity}
            else:
                metrics[f'text_{question.id}'] = {'correct': False, 'match_type': 'empty_response'}

        elif question.question_type == 'graphic':
            graphic_data = request.form.get(f'graphic_{question.id}')
            if graphic_data:
                try:
                    user_contours = json.loads(graphic_data)
                    answers[f'graphic_{question.id}'] = user_contours

                    # Оценка графического ответа
                    result = evaluate_graphic_answer_with_metrics(question.id, user_contours)
                    metrics[f'graphic_{question.id}'] = result

                    # Добавление балла за графический вопрос
                    score += result.get('comprehensive_score', 0)

                except json.JSONDecodeError:
                    answers[f'graphic_{question.id}'] = None
                    metrics[f'graphic_{question.id}'] = {'error': 'invalid_json', 'partial_score': 0.0}

    # Расчет общего балла
    final_score = score / total_questions if total_questions > 0 else 0

    # Расчет продолжительности
    completed_at = datetime.utcnow()
    duration_seconds = (completed_at - started_at).total_seconds()

    # Сохранение результата
    test_result = TestResult(
        user_id=current_user.id,
        test_id=test_id,
        score=final_score,
        answers_json=json.dumps(answers),
        metrics_json=json.dumps(metrics),
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=int(duration_seconds)
    )
    db.session.add(test_result)
    db.session.commit()

    flash(f'Тест завершен! Балл: {score:.2f}/{total_questions} ({final_score*100:.1f}%)')
    return redirect(url_for('student.view_tests'))

@bp.route('/tests/results')
@login_required
def view_results():
    """
    Маршрут для просмотра списка результатов тестов
    """
    if current_user.role != 'student':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    results = TestResult.query.filter_by(user_id=current_user.id).order_by(TestResult.completed_at.desc()).all()
    return render_template('student/results_list.html', results=results)

@bp.route('/results/<int:result_id>')
@login_required
def view_result_detail(result_id):
    """
    Маршрут для просмотра деталей результата теста
    """
    result = TestResult.query.get_or_404(result_id)

    if result.user_id != current_user.id:
        flash('Доступ запрещен')
        return redirect(url_for('student.view_results'))

    test = Test.query.get(result.test_id)
    answers = json.loads(result.answers_json) if result.answers_json else {}
    metrics = json.loads(result.metrics_json) if result.metrics_json else {}

    return render_template('student/result_detail.html', result=result, test=test, answers=answers, metrics=metrics)