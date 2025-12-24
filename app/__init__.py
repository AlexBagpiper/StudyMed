# app/__init__.py
"""
Инициализация Flask-приложения медицинского тестирования
Создание экземпляра приложения, инициализация расширений
"""
from flask import Flask, session # Импортируем session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_babel import _, Babel # Импортируем Babel
from config import Config
from werkzeug.security import generate_password_hash
import os
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

     # Поддерживаемые языки (берём из конфига)
    SUPPORTED_LANGUAGES = list(app.config.get('LANGUAGES', {}).keys())

    # Инициализация расширений
    db.init_app(app)
    # === Включение внешних ключей для SQLite ===
    if 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI'):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = _('Пожалуйста, войдите для доступа к этой странице.')

    # === Babel: get_locale ДО инициализации ===
    def get_locale():
        # 1. Сессия
        lang = session.get('language')
        if lang in app.config.get('LANGUAGES', {}):
            return lang

        # 2. Текущий пользователь (если есть и авторизован)
        try:
            from flask_login import current_user
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                if current_user.language in app.config.get('LANGUAGES', {}):
                    return current_user.language
        except RuntimeError:
            # Вне контекста запроса (например, при CLI-инициализации)
            pass

        # 3. Дефолт
        return app.config.get('BABEL_DEFAULT_LOCALE', 'ru')

    babel = Babel(app, locale_selector=get_locale)
    app.jinja_env.globals['get_locale'] = get_locale

    # Функция для имени приложения
    def get_app_name():
        return app.config.get('APP_NAME', 'Приложение')

    app.jinja_env.globals['get_app_name'] = get_app_name

    # === Регистрация Blueprints ===
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

    # === Jinja2 фильтры ===
    @app.template_filter('from_json')
    def from_json_filter(value):
        try:
            return json.loads(value) if value else []
        except (TypeError, ValueError):
            return []

    # === Создание папок загрузки ===
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'images'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'annotations'), exist_ok=True)

    # === Инициализация БД ===
    with app.app_context():
        # Импорт моделей (чтобы SQLAlchemy их увидел)
        from app.models.user import User
        from app.models.test_topics import TestTopic
        from app.models.question import Question
        from app.models.annotation import ImageAnnotation, TestResult
        from app.models.test_variant import Test, Variant

        db.create_all()

        # === Создание администратора по умолчанию ===
        # Используем хэшированный пароль 'admin'
        admin_username = 'admin'
        admin_password = 'admin'  # ← plaintext, но хэшируем!
        admin_email = admin_username  # для совместимости (логин = email)

        existing_admin = User.query.filter_by(username=admin_email).first()
        if not existing_admin:
            admin_user = User(
                username=admin_email,
                role='admin',
                first_name='Администратор',
                last_name='Системы'
            )
            # ✅ Хэшируем пароль!
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            try:
                db.session.commit()
                app.logger.info(f"Создан администратор: {admin_email} (пароль: '{admin_password}')")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Ошибка создания администратора: {e}")

    return app

# Функция загрузки пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    if user_id is None:
        return None
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None