# app/routes/student.py
"""
Маршруты студента приложения медицинского тестирования
Содержит логику прохождения тестов и просмотра результатов
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models.test import Test
from app.models.question import Question
from app.models.annotation import ImageAnnotation, TestResult
from app.utils.contour_metrics import evaluate_graphic_answer_with_metrics, calculate_comprehensive_contour_score
from config import Config
from datetime import datetime
import json
from flask_babel import _, get_locale # Импортируем _ и get_locale

# Создание Blueprint для маршрутов студента
bp = Blueprint('student', __name__)

@bp.route('/tests')
@login_required
def view_tests():
    """
    Маршрут для просмотра доступных тестов
    """
    # Студенты видят все тесты
    tests = Test.query.all()
    return render_template('student/tests.html', tests=tests)

@bp.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    """
    Маршрут для прохождения теста

    Отображает тест с вопросами для прохождения
    """
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()

    # Разделение вопросов по типам
    graphic_questions = [q for q in questions if q.question_type == 'graphic']
    open_questions = [q for q in questions if q.question_type == 'open']

    # Добавление аннотаций к графическим вопросам
    for question in graphic_questions:
        try:
            annotation_id = int(question.correct_answer)
            question.annotation = ImageAnnotation.query.get(annotation_id)
        except (ValueError, TypeError):
            question.annotation = None

    return render_template('student/test.html',
                          test=test,
                          graphic_questions=graphic_questions,
                          open_questions=open_questions)

@bp.route('/submit_test/<int:test_id>', methods=['POST'])
@login_required
def submit_test(test_id):
    """
    Маршрут для отправки результатов теста

    Обрабатывает ответы студента и сохраняет результаты
    """
    test = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()

    score = 0
    total_questions = len(questions)
    answers = {}
    metrics = {}

    # Запись времени начала если не записано
    started_at = datetime.utcnow()

    # Обработка всех вопросов
    for question in questions:
        if question.question_type == 'open':
            # Обработка открытых вопросов
            user_answer = request.form.get(f'open_{question.id}')
            answers[f'open_{question.id}'] = user_answer

            # Сравнение текстовых ответов
            if user_answer and question.correct_answer:
                # Проверка точного совпадения
                if user_answer.lower().strip() == question.correct_answer.lower().strip():
                    score += 1
                    metrics[f'open_{question.id}'] = {
                        'correct': True,
                        'match_type': 'exact',
                        'user_answer': user_answer,
                        'correct_answer': question.correct_answer,
                        'partial_score': 1.0
                    }
                else:
                    # Расчет частичного совпадения для открытых вопросов
                    correct_answer = question.correct_answer.lower().strip()
                    user_answer_clean = user_answer.lower().strip()

                    # Расчет схожести как отношение общих символов
                    common_chars = sum(1 for c in user_answer_clean if c in correct_answer)
                    similarity = common_chars / len(correct_answer) if len(correct_answer) > 0 else 0

                    # Ограничение схожести до 0.5 для частичного балла
                    partial_score = min(similarity, 0.5)

                    score += partial_score
                    metrics[f'open_{question.id}'] = {
                        'correct': False,
                        'match_type': 'partial',
                        'user_answer': user_answer,
                        'correct_answer': question.correct_answer,
                        'partial_score': partial_score,
                        'similarity': similarity
                    }
            else:
                metrics[f'open_{question.id}'] = {
                    'correct': False,
                    'match_type': 'empty_response',
                    'user_answer': user_answer,
                    'correct_answer': question.correct_answer,
                    'partial_score': 0.0
                }

        elif question.question_type == 'graphic':
            # Обработка графических вопросов
            graphic_data = request.form.get(f'graphic_{question.id}')
            if graphic_data:
                try:
                    user_contours = json.loads(graphic_data)
                    answers[f'graphic_{question.id}'] = user_contours

                    # Оценка графического ответа с детальными метриками
                    result = evaluate_graphic_answer_with_metrics(question.id, user_contours)
                    metrics[f'graphic_{question.id}'] = result

                    # Добавление частичного балла к общему результату
                    score += result.get('comprehensive_score', 0)

                except json.JSONDecodeError:
                    # Если не удается разобрать JSON, ответ считается неправильным
                    answers[f'graphic_{question.id}'] = None
                    metrics[f'graphic_{question.id}'] = {
                        'error': 'invalid_json',
                        'partial_score': 0.0
                    }

    # Расчет финального балла в процентах
    final_score = score / total_questions if total_questions > 0 else 0

    # Расчет продолжительности
    completed_at = datetime.utcnow()
    duration_seconds = (completed_at - started_at).total_seconds()

    # Сохранение результата теста
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

    return jsonify({
        'success': True,
        'message': f'Тест завершен! Балл: {score:.2f}/{total_questions} ({final_score*100:.1f}%)',
        'score': final_score
    })

@bp.route('/results')
@login_required
def view_results():
    """
    Маршрут для просмотра результатов тестов

    Отображает результаты текущего пользователя
    """
    # Студенты видят только свои результаты
    results = TestResult.query.filter_by(user_id=current_user.id).all()

    return render_template('student/results.html', results=results)

@bp.route('/results/<int:result_id>')
@login_required
def view_result_details(result_id):
    """
    Маршрут для просмотра деталей результата теста

    Отображает подробную информацию о результатах теста
    """
    result = TestResult.query.get_or_404(result_id)

    # Проверка прав доступа
    if result.user_id != current_user.id:
        flash(_('Доступ запрещен'))
        return redirect(url_for('student.view_results'))

    answers = json.loads(result.answers_json) if result.answers_json else {}
    metrics = json.loads(result.metrics_json) if result.metrics_json else {}

    return render_template('student/result_details.html',
                          result=result,
                          answers=answers,
                          metrics=metrics)