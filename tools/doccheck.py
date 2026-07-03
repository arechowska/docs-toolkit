#!/usr/bin/env python3
"""
doccheck — универсальный линтер и автофиксер Markdown-документации.

Правила проверки задаются в файле doccheck.toml рядом с проектом —
скрипт не содержит жёстко зашитых правил и работает с любой документацией.

Использование:
  python3 doccheck.py                    # проверить docs/ по правилам из doccheck.toml
  python3 doccheck.py --fix              # автоисправить безопасные ошибки
  python3 doccheck.py --init             # создать пример doccheck.toml
  python3 doccheck.py --config my.toml  # указать другой конфиг
  python3 doccheck.py path/to/file.md   # проверить конкретный файл или папку

Коды выхода:
  0 — ошибок нет
  1 — найдены ошибки (удобно для CI/CD)

Требования:
  Python 3.11+  — зависимостей нет
  Python 3.10   — pip install tomli
"""

import re
import os
import sys
import glob
import argparse
from pathlib import Path

# ── TOML-парсер ────────────────────────────────────────────────────────────────
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        print("Требуется Python 3.11+ или установите: pip install tomli")
        sys.exit(1)

# ── Цвета терминала ────────────────────────────────────────────────────────────
RED = "\033[31m"
YLW = "\033[33m"
GRN = "\033[32m"
BLD = "\033[1m"
DIM = "\033[2m"
RST = "\033[0m"

# ── Шаблон конфига для --init ──────────────────────────────────────────────────
DEFAULT_CONFIG = """\
# doccheck.toml — правила проверки документации
# Документация: github.com/yourname/doc-tools

[project]
name    = "Название проекта"
docs    = "docs/"           # папка с Markdown-файлами
ignore  = []                # папки или файлы, которые пропускать

# ── Автоисправление ────────────────────────────────────────────────────────────
# Эти правила применяются при запуске с флагом --fix.
# pattern   — регулярное выражение (Python re)
# replacement — строка замены
# description — что именно исправляется (выводится в отчёте)

[[fix]]
pattern     = "ё"
replacement = "е"
description = "ё → е"

[[fix]]
pattern     = "Ё"
replacement = "Е"
description = "Ё → Е"

# [[fix]]
# pattern     = '!!! note "Примечание\\."'
# replacement = '!!! note "Примечание"'
# description = "точка в заголовке примечания"

# ── Проверки без автоисправления ───────────────────────────────────────────────
# severity = "error" — блокирует коммит/CI, выход с кодом 1
# severity = "warn"  — выводит предупреждение, не блокирует

[[check]]
pattern     = '!\\[\\]\\('
description = "Изображение без alt-текста"
severity    = "warn"

# [[check]]
# pattern     = '\\*\\*[^*\\n]+\\*\\* —'
# description = "Тире после термина — заменить на двоеточие?"
# severity    = "warn"
"""


# ── Загрузка конфига ───────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    """Загрузить и вернуть конфиг из TOML-файла."""
    path = Path(config_path)
    if not path.exists():
        print(f"{RED}Конфиг не найден:{RST} {config_path}")
        print(f"{DIM}Создайте конфиг командой: python3 doccheck.py --init{RST}")
        sys.exit(1)
    with open(path, "rb") as f:
        return tomllib.load(f)


# ── Работа с файлами ───────────────────────────────────────────────────────────

def find_files(paths: list[str], ignore: list[str]) -> list[str]:
    """Собрать список .md файлов по указанным путям, исключая ignore."""
    result = []
    for path in paths:
        if os.path.isfile(path) and path.endswith(".md"):
            result.append(path)
        elif os.path.isdir(path):
            result.extend(glob.glob(f"{path}/**/*.md", recursive=True))

    if ignore:
        ignore_norm = [os.path.normpath(i) for i in ignore]
        result = [
            f for f in result
            if not any(
                os.path.normpath(f) == ign
                or os.path.normpath(f).startswith(ign + os.sep)
                for ign in ignore_norm
            )
        ]
    return sorted(result)


def line_number(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def check_links(filepath: str, text: str) -> list[tuple]:
    """Проверить внутренние ссылки — существуют ли целевые файлы."""
    issues = []
    base_dir = os.path.dirname(filepath)
    for match in re.finditer(r'\]\(([^)#\s]+\.md)(?:#[^)]*)?\)', text):
        link = match.group(1)
        if link.startswith("http"):
            continue
        target = os.path.normpath(os.path.join(base_dir, link))
        if not os.path.exists(target):
            issues.append((
                line_number(text, match.start()),
                f"Битая ссылка: {link}",
                "error",
            ))
    return issues


def process_file(
    filepath: str,
    fix_rules: list[dict],
    check_rules: list[dict],
    fix: bool,
) -> tuple[list, list]:
    """
    Проверить файл. Если fix=True — применить автоисправления.
    Возвращает (issues, fixes_applied).
    """
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    original = text
    fixes_applied = []
    issues = []

    if fix:
        for rule in fix_rules:
            new_text, count = re.subn(rule["pattern"], rule["replacement"], text)
            if count:
                fixes_applied.append(f"{rule['description']} ({count}×)")
                text = new_text
        if text != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
    else:
        for rule in fix_rules:
            for match in re.finditer(rule["pattern"], text):
                issues.append((
                    line_number(text, match.start()),
                    rule["description"],
                    "error",
                ))

    for rule in check_rules:
        for match in re.finditer(rule["pattern"], text):
            issues.append((
                line_number(text, match.start()),
                rule["description"],
                rule.get("severity", "warn"),
            ))

    issues.extend(check_links(filepath, text))
    issues.sort()

    return issues, fixes_applied


# ── Вывод результатов ──────────────────────────────────────────────────────────

def print_file_result(filepath: str, issues: list, fixes: list) -> None:
    """Вывести результат проверки одного файла в терминал."""
    rel = os.path.relpath(filepath)
    has_errors = any(s == "error" for _, _, s in issues)

    if fixes:
        print(f"{GRN}✓ {rel}{RST}")
        for fix in fixes:
            print(f"  {GRN}исправлено:{RST} {fix}")

    if issues:
        color = RED if has_errors else YLW
        print(f"{color}✗ {rel}{RST}")
        for line_num, desc, severity in issues:
            c = RED if severity == "error" else YLW
            mark = "×" if severity == "error" else "!"
            print(f"  {c}{mark}{RST} {DIM}строка {line_num}:{RST} {desc}")


# ── Точка входа ────────────────────────────────────────────────────────────────

def main() -> None:
    """Точка входа: разобрать аргументы и запустить проверку."""
    parser = argparse.ArgumentParser(
        description="doccheck — линтер и автофиксер Markdown-документации",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "paths", nargs="*",
        metavar="PATH",
        help="Файлы или папки для проверки (по умолчанию берётся из конфига)",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Автоматически исправить ошибки из раздела [[fix]] в конфиге",
    )
    parser.add_argument(
        "--config", default="doccheck.toml", metavar="FILE",
        help="Путь к конфиг-файлу (по умолчанию: doccheck.toml)",
    )
    parser.add_argument(
        "--init", action="store_true",
        help="Создать пример doccheck.toml в текущей папке",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Показывать только файлы с проблемами",
    )
    args = parser.parse_args()

    if args.init:
        target = Path("doccheck.toml")
        if target.exists():
            print(f"{YLW}doccheck.toml уже существует — не перезаписываю{RST}")
        else:
            target.write_text(DEFAULT_CONFIG, encoding="utf-8")
            print(f"{GRN}✓ Создан doccheck.toml — отредактируй правила под свой проект{RST}")
        sys.exit(0)

    config = load_config(args.config)
    project = config.get("project", {})

    docs_dir = project.get("docs", "docs/")
    ignore   = project.get("ignore", [])
    paths    = args.paths or [docs_dir]

    fix_rules   = config.get("fix", [])
    check_rules = config.get("check", [])

    files = find_files(paths, ignore)
    if not files:
        print(f"{YLW}Файлы .md не найдены{RST}")
        sys.exit(0)

    total_issues = 0
    total_fixes  = 0
    files_with_issues = 0

    for filepath in files:
        issues, fixes = process_file(filepath, fix_rules, check_rules, fix=args.fix)

        if not args.quiet or issues or fixes:
            print_file_result(filepath, issues, fixes)

        total_issues += len(issues)
        total_fixes  += len(fixes)
        if issues:
            files_with_issues += 1

    print()
    name = project.get("name", "")
    label = f"{BLD}{name}{RST} — " if name else ""
    print(f"{label}{BLD}проверено:{RST} {len(files)} файлов", end="")

    if args.fix and total_fixes:
        print(f"  {GRN}{BLD}исправлено:{RST} {total_fixes} правок", end="")

    if total_issues:
        print(f"  {RED}{BLD}проблем:{RST} {total_issues} в {files_with_issues} файлах")
        if not args.fix and fix_rules:
            print(f"{DIM}Запустите с --fix чтобы исправить автоматически{RST}")
        sys.exit(1)
    else:
        print(f"  {GRN}{BLD}всё в порядке{RST}")


if __name__ == "__main__":
    main()
