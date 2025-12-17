# config.py
import os
from datetime import timedelta

class Config:
    """Базовый класс конфигурации приложения"""

    # Название приложения
    APP_NAME = 'MedTest'

    # Настройки безопасности
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

    # Настройки базы данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///medical_tests.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Настройки загрузки файлов
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Указываем путь к каталогу с переводами
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations')
    BABEL_DEFAULT_LOCALE = 'ru'  # Язык по умолчанию
    BABEL_DEFAULT_TIMEZONE = 'UTC'
    # Поддерживаемые языки
    LANGUAGES = {
        'ru': 'Русский',
        'en': 'English'
    }

    # Настройки темизации
    THEMES_PATH = os.path.join(os.path.dirname(__file__), 'themes')
    DEFAULT_THEME = 'default'

    # Настройки приложения
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Константы приложения
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    ALLOWED_ANNOTATION_EXTENSIONS = {'json', 'txt'}
    CONTOUR_THRESHOLD = 0.5
    LABEL_THRESHOLD = {
        'overlap_ratio': 0.9,
        'area_tolerance': 0.1
    }

    # Веса метрик контуров
    CONTOUR_METRICS_WEIGHTS = {
        'iou': 0.4,
        'boundary_match': 0.3,
        'presence': 0.2,
        'label_match': 0.1
    }