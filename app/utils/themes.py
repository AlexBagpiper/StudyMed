# app/utils/themes.py
"""
Утилиты для управления темами приложения медицинского тестирования
Содержит функции для загрузки и применения тем оформления
"""
import json
import os
from flask import current_app, session

def load_theme(theme_name):
    """
    Загрузка темы из JSON-файла

    Args:
        theme_name (str): Название темы

    Returns:
        dict: Словарь с параметрами темы или None если не найдено
    """
    from config import Config

    theme_file = os.path.join(Config.THEMES_PATH, f'{theme_name}.json')

    if os.path.exists(theme_file):
        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                theme_data = json.load(f)
            return theme_data
        except Exception as e:
            print(f"Ошибка загрузки темы {theme_name}: {e}")
            return None
    else:
        print(f"Файл темы {theme_file} не найден")
        return None

def get_theme_css(theme_name):
    """
    Получение CSS для указанной темы

    Args:
        theme_name (str): Название темы

    Returns:
        str: CSS-код темы или пустая строка если не найдено
    """
    theme_data = load_theme(theme_name)
    if not theme_data:
        return ""

    # Генерация CSS из данных темы
    css_rules = []
    for selector, properties in theme_data.get('css', {}).items():
        css_rule = f"{selector} {{\n"
        for prop, value in properties.items():
            css_rule += f"  {prop}: {value};\n"
        css_rule += "}\n"
        css_rules.append(css_rule)

    return "\n".join(css_rules)

def apply_theme_to_response(response):
    """
    Применение текущей темы к HTTP-ответу

    Args:
        response: HTTP-ответ Flask

    Returns:
        response: Измененный HTTP-ответ с примененной темой
    """
    # Получение текущей темы из сессии
    current_theme = session.get('theme', 'default')

    # Загрузка CSS темы
    theme_css = get_theme_css(current_theme)

    # Добавление CSS к ответу (в реальной реализации может потребоваться изменение HTML)
    if theme_css:
        response.set_cookie('current_theme', current_theme)

    return response