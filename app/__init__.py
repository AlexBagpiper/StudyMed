# app/__init__.py
"""
Инициализация Flask-приложения медицинского тестирования
Создание экземпляра приложения, инициализация расширений
"""
from flask import Flask, session # Импортируем session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_babel import Babel # Импортируем Babel
from config import Config
import json

# Инициализация расширений Flask (до create_app)
db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_class=Config):
    """
    Создание и настройка экземпляра Flask-приложения

    Args:
        config_class: Класс конфигурации приложения

    Returns:
        app: Настроенный экземпляр Flask-приложения
    """
    # Создание экземпляра приложения
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Поддерживаемые языки (берем из конфига)
    SUPPORTED_LANGUAGES = list(app.config['LANGUAGES'].keys())

    # Инициализация расширений с приложением
    db.init_app(app)
    login_manager.init_app(app)
    # ВАЖНО: инициализируем babel с приложением ПЕРЕД определением get_locale

    # Настройка LoginManager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

    # --- ОПРЕДЕЛЕНИЕ ФУНКЦИИ get_locale ПОСЛЕ babel.init_app ---
    # Определяем функцию get_locale ВНУТРИ create_app ПОСЛЕ babel.init_app
    def get_locale():
        # Попробовать получить язык из сессии
        user_language = session.get('language')
        # Если в сессии нет языка, использовать язык по умолчанию
        if user_language in SUPPORTED_LANGUAGES:
            return user_language
        return app.config['BABEL_DEFAULT_LOCALE']

    # Определяем функцию get_app_name для подстановки имени приложения
    def get_app_name():
        return app.config['APP_NAME']
    # Регистрируем функцию в globals
    app.jinja_env.globals['get_app_name'] = get_app_name

    babel = Babel(app, locale_selector=get_locale)
    app.jinja_env.globals['get_locale'] = get_locale

    # Регистрация blueprints (модулей)
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.routes.teacher import bp as teacher_bp
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    from app.routes.student import bp as student_bp
    app.register_blueprint(student_bp, url_prefix='/student')

    from app.routes.database import bp as database_bp
    app.register_blueprint(database_bp, url_prefix='/database')

    # Добавление фильтра для Jinja2 для преобразования JSON в Python объект
    @app.template_filter('from_json')
    def from_json_filter(value):
        """
        Фильтр Jinja2 для преобразования JSON строки в Python объект

        Args:
            value (str): JSON строка

        Returns:
            object: Python объект из JSON
        """
        try:
            return json.loads(value)
        except:
            return []

    # Создание папки для загрузки файлов если не существует
    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Создание базы данных и добавление начальных данных (без администратора)
    with app.app_context():
        # Импорт моделей для создания таблиц
        from app.models.user import User
        from app.models.test import Test
        from app.models.question import Question
        from app.models.annotation import ImageAnnotation, TestResult

        # Создание всех таблиц
        db.create_all()

        # Создание администратора по умолчанию из файла admin_credentials.py
        from admin_credentials import ADMIN_CREDENTIALS
        admin_user = User.query.filter_by(username=ADMIN_CREDENTIALS['username']).first() # Меняем на email
        if not admin_user:
            admin_user = User(
                username=ADMIN_CREDENTIALS['username'], # Меняем на email
                password_hash=ADMIN_CREDENTIALS['password'],
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()

    return app

# Функция загрузки пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """
    Загрузка пользователя по ID для Flask-Login

    Args:
        user_id: ID пользователя

    Returns:
        User: Объект пользователя или None если не найден
    """
    from app.models.user import User
    return User.query.get(int(user_id))