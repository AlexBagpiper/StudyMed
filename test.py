# app/routes/database.py (обновленный)
"""
Маршруты управления базой данных приложения медицинского тестирования
Содержит инструменты просмотра и редактирования данных
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test import Test
from app.models.question import Question
from app.models.annotation import ImageAnnotation, TestResult
from config import Config
import os
import json

# Создание Blueprint для маршрутов управления базой данных
bp = Blueprint('database', __name__)

@bp.route('/database')
@login_required
def index():
    """
    Главная страница управления базой данных - отображает статистику
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Получение статистики (без вызова связанных объектов, которые могут вызвать ошибку)
    users_count = db.session.query(User.id).count()
    tests_count = db.session.query(Test.id).count()
    questions_count = db.session.query(Question.id).count()
    annotations_count = db.session.query(ImageAnnotation.id).count()
    results_count = db.session.query(TestResult.id).count()

    return render_template('database/index.html',
                          users_count=users_count,
                          tests_count=tests_count,
                          questions_count=questions_count,
                          annotations_count=annotations_count,
                          results_count=results_count)

@bp.route('/database/users')
@login_required
def view_users():
    """
    Маршрут для просмотра списка пользователей
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Загрузка пользователей без связанных объектов для избежания ошибок
    users = db.session.query(User.id, User.username, User.role, User.language, User.theme, User.created_at).all()
    # Если нужно отобразить количество связанных записей, можно использовать подзапросы
    # Но для простого просмотра списка это не обязательно
    return render_template('database/users.html', users=users)

@bp.route('/database/tests')
@login_required
def view_tests():
    """
    Маршрут для просмотра списка тестов
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Загрузка тестов без связанных объектов для избежания ошибок
    tests = db.session.query(Test.id, Test.title, Test.description, Test.created_at).all()
    return render_template('database/tests.html', tests=tests)

@bp.route('/database/questions')
@login_required
def view_questions():
    """
    Маршрут для просмотра списка вопросов
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Загрузка вопросов с информацией о тесте (без полной загрузки объекта Test)
    questions = db.session.query(
        Question.id,
        Question.test_id,
        Question.question_text,
        Question.question_type,
        Test.title.label('test_title') # Подзапрос для получения названия теста
    ).outerjoin(Test).all() # outerjoin для включения вопросов без теста (если такие есть)
    return render_template('database/questions.html', questions=questions)

@bp.route('/database/annotations')
@login_required
def view_annotations():
    """
    Маршрут для просмотра списка аннотаций
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    annotations = ImageAnnotation.query.all()
    return render_template('database/annotations.html', annotations=annotations)

@bp.route('/database/results')
@login_required
def view_results():
    """
    Маршрут для просмотра списка результатов тестов
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    # Загрузка результатов с информацией о пользователе и тесте (без полной загрузки объектов)
    results = db.session.query(
        TestResult.id,
        TestResult.user_id,
        TestResult.test_id,
        TestResult.score,
        TestResult.completed_at,
        TestResult.duration_seconds,
        User.username.label('user_username'), # Подзапрос для получения имени пользователя
        Test.title.label('test_title')        # Подзапрос для получения названия теста
    ).outerjoin(User).outerjoin(Test).all() # outerjoin для включения результатов без пользователя или теста (если такие есть)

    return render_template('database/results.html', results=results)

@bp.route('/database/delete/<table>/<int:id>')
@login_required
def delete_record(table, id):
    """
    Маршрут для удаления записи из таблицы

    Args:
        table (str): Название таблицы
        id (int): ID записи
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.index'))

    try:
        if table == 'users':
            record = User.query.get_or_404(id)
            db.session.delete(record)
        elif table == 'tests':
            record = Test.query.get_or_404(id)
            db.session.delete(record)
        elif table == 'questions':
            record = Question.query.get_or_404(id)
            db.session.delete(record)
        elif table == 'annotations':
            record = ImageAnnotation.query.get_or_404(id)
            db.session.delete(record)
        elif table == 'results':
            record = TestResult.query.get_or_404(id)
            db.session.delete(record)
        else:
            flash('Неверная таблица')
            return redirect(url_for('database.index'))

        db.session.commit()
        flash(f'Запись из таблицы {table} успешно удалена')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении: {str(e)}')

    return redirect(url_for(f'database.view_{table}'))

@bp.route('/database/edit/<table>/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_record(table, id):
    """
    Маршрут для редактирования записи в таблице

    Args:
        table (str): Название таблицы
        id (int): ID записи
    """
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
            elif table == 'tests':
                record = Test.query.get_or_404(id)
                record.title = request.form['title']
                record.description = request.form['description']
            elif table == 'questions':
                record = Question.query.get_or_404(id)
                record.question_text = request.form['question_text']
                record.question_type = request.form['question_type']
                record.correct_answer = request.form['correct_answer']
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
                # Обработка started_at и completed_at если они передаются
                started_at_str = request.form.get('started_at')
                completed_at_str = request.form.get('completed_at')
                if started_at_str:
                    record.started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                if completed_at_str:
                    record.completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00'))
                record.duration_seconds = int(request.form.get('duration_seconds', 0))
            else:
                flash('Неверная таблица')
                return redirect(url_for('database.index'))

            db.session.commit()
            flash(f'Запись в таблице {table} успешно обновлена')
            return redirect(url_for(f'database.view_{table}'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении: {str(e)}')

    # Отображение формы редактирования
    if table == 'users':
        record = User.query.get_or_404(id)
        return render_template('database/edit_user.html', user=record)
    elif table == 'tests':
        record = Test.query.get_or_404(id)
        return render_template('database/edit_test.html', test=record)
    elif table == 'questions':
        record = Question.query.get_or_404(id)
        # Загружаем связанный тест для отображения в форме
        test = Test.query.get(record.test_id) if record.test_id else None
        return render_template('database/edit_question.html', question=record, test=test)
    elif table == 'annotations':
        record = ImageAnnotation.query.get_or_404(id)
        return render_template('database/edit_annotation.html', annotation=record)
    elif table == 'results':
        record = TestResult.query.get_or_404(id)
        # Загружаем связанные пользователь и тест для отображения в форме
        user = User.query.get(record.user_id) if record.user_id else None
        test = Test.query.get(record.test_id) if record.test_id else None
        return render_template('database/edit_result.html', result=record, user=user, test=test)
    else:
        flash('Неверная таблица')
        return redirect(url_for('database.index'))