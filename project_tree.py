#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from pathlib import Path

# Служебные директории, которые исключаются по умолчанию
DEFAULT_IGNORE_DIRS = {
    '.git', '__pycache__', 'node_modules', 'venv', '.venv',
    '.mypy_cache', '.pytest_cache', '.tox', '.eggs', 'dist', 'build',
    '.vscode', '.idea', '.DS_Store', 'Thumbs.db',
}

DEFAULT_IGNORE_FILES = {
    '.DS_Store', 'Thumbs.db',
}


def should_ignore(path: Path, ignore_dirs, ignore_files, show_hidden=False):
    """Определяет, следует ли игнорировать путь."""
    name = path.name

    # Игнорируем скрытые файлы/папки, если не включён флаг --show-hidden
    if not show_hidden and name.startswith('.') and name not in {'.env', '.gitignore', '.editorconfig'}:
        return True

    if path.is_dir() and name in ignore_dirs:
        return True

    if path.is_file() and name in ignore_files:
        return True

    return False


def build_tree(
    root_path: Path,
    prefix="",
    is_last=True,
    output_lines=None,
    *,
    include_ext=None,
    exclude_ext=None,
    ignore_dirs=None,
    ignore_files=None,
    show_hidden=False,
):
    if output_lines is None:
        output_lines = []

    if not root_path.is_dir():
        output_lines.append(f"[!] '{root_path}' не является директорией.")
        return output_lines

    try:
        items = sorted(root_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError as e:
        output_lines.append(f"{prefix}{'└── ' if is_last else '├── '}⚠️  [Доступ запрещён: {e}]")
        return output_lines

    filtered_items = []
    for item in items:
        if should_ignore(item, ignore_dirs, ignore_files, show_hidden):
            continue

        if item.is_file():
            ext = item.suffix.lower()
            if include_ext and ext not in include_ext:
                continue
            if exclude_ext and ext in exclude_ext:
                continue

        filtered_items.append(item)

    total = len(filtered_items)

    for i, item in enumerate(filtered_items):
        is_last_item = (i == total - 1)
        connector = "└── " if is_last_item else "├── "
        name = item.name
        display_name = name + ("/" if item.is_dir() else "")
        output_lines.append(prefix + connector + display_name)

        if item.is_dir():
            new_prefix = prefix + ("    " if is_last_item else "│   ")
            build_tree(
                item,
                new_prefix,
                is_last_item,
                output_lines,
                include_ext=include_ext,
                exclude_ext=exclude_ext,
                ignore_dirs=ignore_dirs,
                ignore_files=ignore_files,
                show_hidden=show_hidden,
            )

    return output_lines


def parse_extension_list(ext_list):
    if not ext_list:
        return set()
    result = set()
    for e in ext_list:
        e = e.strip().lower()
        if e and not e.startswith('.'):
            e = '.' + e
        result.add(e)
    return result


def main():
    # Формируем подробный epilog на русском языке
    epilog_text = """
СПРАВКА

Назначение:
  Скрипт генерирует древовидную текстовую структуру файлов и каталогов проекта.
  Предназначен для документирования, анализа и контроля версий.

Правила фильтрации по умолчанию:
  • Исключаются служебные каталоги: .git, __pycache__, node_modules, venv, dist, build, .vscode, .idea и др.
  • Скрытые файлы (начинающиеся с '.') скрыты, кроме: .env, .gitignore, .editorconfig.
  • Файлы .DS_Store (macOS) и Thumbs.db (Windows) исключаются всегда.

Формат расширений:
  Указывайте расширения с точкой или без: "py", ".py", "txt", ".log" — эквивалентно.

Приоритет фильтров:
  1. Исключить по --exclude-ext (имеет наивысший приоритет).
  2. Оставить только по --include-ext (если задан).
  3. Применить правила игнорирования служебных элементов.

Примеры:
  python project_tree.py
      → структура текущей папки, стандартная фильтрация

  python project_tree.py src -o tree.txt --include-ext py json
      → только .py и .json в папке src

  python project_tree.py --show-hidden
      → показать .env, .gitignore и т.п.

  python project_tree.py --no-ignore
      → отключить все стандартные исключения (включая .git и __pycache__)

  python project_tree.py -o full.txt --show-hidden --no-ignore
      → полная структура без фильтрации

Технические примечания:
  • Выходной файл кодируется в UTF-8.
  • Директории в выводе помечаются символом '/' на конце.
  • При ошибках доступа отображается предупреждение, обход продолжается.
""".strip()

    parser = argparse.ArgumentParser(
        prog="project_tree.py",
        description="Генерация текстовой структуры проекта с фильтрацией по расширениям и исключением служебных артефактов.",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True
    )

    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        metavar="КОРНЕВАЯ_ПАПКА",
        help="Путь к корневой директории (по умолчанию: текущая '.')."
    )
    parser.add_argument(
        "-o", "--output",
        default="structure.txt",
        metavar="ФАЙЛ",
        help="Имя выходного файла (по умолчанию: structure.txt)."
    )
    parser.add_argument(
        "--include-ext",
        nargs="*",
        metavar="РАСШ",
        help="Включить ТОЛЬКО файлы с указанными расширениями (например: py txt md)."
    )
    parser.add_argument(
        "--exclude-ext",
        nargs="*",
        metavar="РАСШ",
        help="Исключить файлы с указанными расширениями (например: log tmp pyc)."
    )
    parser.add_argument(
        "--show-hidden",
        action="store_true",
        help="Показывать скрытые файлы (кроме игнорируемых служебных, например .git)."
    )
    parser.add_argument(
        "--no-ignore",
        action="store_true",
        help="Отключить стандартное исключение (.git, __pycache__, node_modules и др.)."
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"[Ошибка] Путь не существует: {root}", file=sys.stderr)
        sys.exit(1)

    ignore_dirs = set() if args.no_ignore else DEFAULT_IGNORE_DIRS.copy()
    ignore_files = set() if args.no_ignore else DEFAULT_IGNORE_FILES.copy()
    include_ext = parse_extension_list(args.include_ext)
    exclude_ext = parse_extension_list(args.exclude_ext)

    lines = [
        f"Структура проекта: {root}",
        "=" * 60,
        f"Включённые расширения: {sorted(include_ext) if include_ext else 'все'}",
        f"Исключённые расширения: {sorted(exclude_ext) if exclude_ext else 'нет'}",
        f"Скрытые файлы: {'показаны' if args.show_hidden else 'скрыты'}",
        f"Игнорируемые директории: {sorted(ignore_dirs) if not args.no_ignore else 'отключено'}",
        "=" * 60,
    ]

    build_tree(
        root,
        output_lines=lines,
        include_ext=include_ext,
        exclude_ext=exclude_ext,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
        show_hidden=args.show_hidden,
    )

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"✅ Структура сохранена в '{args.output}'")
        print(f"   Всего строк: {len(lines)}")
    except Exception as e:
        print(f"[Ошибка записи в '{args.output}']: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()