# update_translations.py
import os
import subprocess
import sys
import re

# Путь к файлу конфигурации Babel
BABEL_CONFIG = 'babel.cfg'
# Папка, где хранятся переводы
TRANSLATIONS_DIR = 'translations'
# Поддерживаемые языки
LANGUAGES = ['ru', 'en']

def run_command(cmd, description=""):
    """Выполняет команду и выводит результат."""
    print(f"Выполняю: {description}")
    print(f"Команда: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print("Успешно выполнено.")
        if result.stdout:
            print("STDOUT (первые 500 символов):", result.stdout[:500])
        if result.stderr:
            print("STDERR (первые 500 символов):", result.stderr[:500])
    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения команды: {e}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)

def find_empty_translations(po_file_path):
    """Находит строки с пустыми msgstr в файле .po."""
    empty_entries = []
    with open(po_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Регулярное выражение для поиска блоков msgid/msgstr
    # Упрощённое, может не учитывать многострочные строки напрямую, но подходит для базового поиска
    pattern = r'msgid\s+"([^"]*)"[^m]*?msgstr\s+""'
    matches = re.findall(pattern, content)
    if matches:
        print(f"  Найдено {len(matches)} пустых переводов в {po_file_path}:")
        for msgid in matches[:10]: # Показываем первые 10
            print(f"    - {msgid}")
        if len(matches) > 10:
            print(f"    ... и ещё {len(matches) - 10}")
    else:
        print(f"  В {po_file_path} не найдено пустых переводов.")

def main():
    print("=== Обновление файлов локализации ===")

    # 1. Извлечение строк
    print("\n1. Извлечение строк для перевода...")
    extract_cmd = f"pybabel extract -F {BABEL_CONFIG} -k _l -o {TRANSLATIONS_DIR}/messages.pot ."
    run_command(extract_cmd, "Извлечение строк в messages.pot")

    # 2. Инициализация новых языков (если файлы .po еще не созданы)
    for lang in LANGUAGES:
        po_file = os.path.join(TRANSLATIONS_DIR, lang, 'LC_MESSAGES', 'messages.po')
        if not os.path.exists(po_file):
            print(f"\n2. Инициализация каталога для языка {lang}...")
            init_cmd = f"pybabel init -i {TRANSLATIONS_DIR}/messages.pot -d {TRANSLATIONS_DIR} -l {lang}"
            run_command(init_cmd, f"Инициализация {lang}")
        else:
            print(f"\n2. Файл {po_file} уже существует, пропускаю инициализацию для {lang}.")

    # 3. Обновление существующих .po файлов
    print(f"\n3. Обновление файлов .po для языков: {', '.join(LANGUAGES)}...")
    update_cmd = f"pybabel update -i {TRANSLATIONS_DIR}/messages.pot -d {TRANSLATIONS_DIR} -l {' -l '.join(LANGUAGES)}"
    run_command(update_cmd, "Обновление .po файлов")

    # 4. Проверка пустых переводов в обновленных .po файлах
    print(f"\n4. Проверка пустых переводов в обновленных файлах .po...")
    for lang in LANGUAGES:
        po_file = os.path.join(TRANSLATIONS_DIR, lang, 'LC_MESSAGES', 'messages.po')
        if os.path.exists(po_file):
            print(f"  Проверяю {po_file}...")
            find_empty_translations(po_file)
        else:
            print(f"  Файл {po_file} не найден для проверки.")

    print("\n--- ВАЖНО ---")
    print("После обновления .po файлов, откройте их в редакторе (например, Poedit или вручную).")
    print("Заполните пустые 'msgstr \"\"' подходящими переводами.")
    print("Для русского файла (ru/LC_MESSAGES/messages.po):")
    print("  - Если 'msgid' - английская строка (например, 'Login'), заполните 'msgstr' русским переводом (например, 'Вход').")
    print("  - Если 'msgid' - русская строка (например, 'Вход'), и вы хотите, чтобы она оставалась без перевода, оставьте 'msgstr' пустым.")
    print("  - Однако, лучшая практика - использовать английские 'msgid' в шаблонах и коде, даже если сайт изначально на русском.")
    print("----------------")

    # 5. Компиляция .po файлов в .mo
    print(f"\n5. Компиляция .po файлов в .mo для языков: {', '.join(LANGUAGES)}...")
    compile_cmd = f"pybabel compile -d {TRANSLATIONS_DIR}"
    run_command(compile_cmd, "Компиляция .mo файлов")

    print("\n=== Обновление локализации завершено ===")
    print("Убедитесь, что вы заполнили недостающие переводы в файлах .po перед следующим запуском приложения.")


if __name__ == "__main__":
    main()