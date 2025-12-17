# app/routes/database.py
"""
Маршруты для просмотра и управления базой данных
Содержит инструменты просмотра и редактирования данных в БД
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.test import Test
from app.models.question import Question
from app.models.annotation import ImageAnnotation, TestResult

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
    tests_count = Test.query.count()
    questions_count = Question.query.count()
    annotations_count = ImageAnnotation.query.count()
    results_count = TestResult.query.count()

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
    Просмотр пользователей
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

    users = User.query.all()
    return render_template('database/users.html', users=users)

@bp.route('/database/tests')
@login_required
def view_tests():
    """
    Просмотр тестов
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

    tests = Test.query.all()
    return render_template('database/tests.html', tests=tests)

@bp.route('/database/questions')
@login_required
def view_questions():
    """
    Просмотр вопросов
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

    questions = Question.query.all()
    return render_template('database/questions.html', questions=questions)

@bp.route('/database/annotations')
@login_required
def view_annotations():
    """
    Просмотр аннотаций
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

    annotations = ImageAnnotation.query.all()
    return render_template('database/annotations.html', annotations=annotations)

@bp.route('/database/results')
@login_required
def view_results():
    """
    Просмотр результатов тестов
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

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
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

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
        flash(f'Запись из таблицы {table} удалена')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении: {str(e)}')

    return redirect(url_for(f'database.view_{table[:-1] if table.endswith("s") else table}s'))

@bp.route('/database/edit/<table>/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_record(table, id):
    """
    Редактирование записи в таблице

    Args:
        table (str): Название таблицы
        id (int): ID записи
    """
    if current_user.role != 'admin':
        flash('Доступ запрещен')
        return redirect(url_for('main.dashboard'))

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
            else:
                flash('Неверная таблица')
                return redirect(url_for('database.index'))

            db.session.commit()
            flash(f'Запись в таблице {table} обновлена')
            return redirect(url_for(f'database.view_{table[:-1] if table.endswith("s") else table}s'))
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
        return render_template('database/edit_question.html', question=record)
    elif table == 'annotations':
        record = ImageAnnotation.query.get_or_404(id)
        return render_template('database/edit_annotation.html', annotation=record)
    elif table == 'results':
        record = TestResult.query.get_or_404(id)
        return render_template('database/edit_result.html', result=record)
    else:
        flash('Неверная таблица')
        return redirect(url_for('database.index'))