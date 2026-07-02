#!/usr/bin/env python3
"""
rename_images — переименование скриншотов после конвертации из Word.

После pandoc изображения называются image1.png, image2.png и т.д.
Скрипт находит ближайший текст (или подпись «Рис. N —») как подсказку,
предлагает читаемое имя, переименовывает файл и обновляет ссылки во всех .md.

Использование:
  python3 tools/rename_images.py docs/                     # все .md файлы
  python3 tools/rename_images.py docs/payments/pay.md      # один файл
  python3 tools/rename_images.py --dry-run docs/           # только просмотр
  python3 tools/rename_images.py --auto docs/              # принять всё без вопросов
  python3 tools/rename_images.py --auto --strip-captions docs/  # + удалить строки Рис.

Управление в диалоге:
  Enter         — принять предложенное имя
  имя_файла     — ввести своё (без расширения)
  s             — пропустить
  Ctrl+C        — выйти
"""

import os
import re
import sys
import glob
import shutil
import argparse

_RU_MAP = {
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'g',  'д': 'd',  'е': 'e',
    'ё': 'e',  'ж': 'zh', 'з': 'z',  'и': 'i',  'й': 'y',  'к': 'k',
    'л': 'l',  'м': 'm',  'н': 'n',  'о': 'o',  'п': 'p',  'р': 'r',
    'с': 's',  'т': 't',  'у': 'u',  'ф': 'f',  'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y',  'ь': '',
    'э': 'e',  'ю': 'yu', 'я': 'ya',
}


def _translit(text: str) -> str:
    return ''.join(_RU_MAP.get(ch.lower(), ch) for ch in text)

# ── Цвета ──────────────────────────────────────────────────────────────────────
GRN = "\033[32m"
YLW = "\033[33m"
RED = "\033[31m"
BLD = "\033[1m"
DIM = "\033[2m"
CYN = "\033[36m"
RST = "\033[0m"

IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
GENERIC_NAME  = re.compile(r'image\d+\.(png|jpg|jpeg|gif)', re.IGNORECASE)

# Слова после которых обрезаем — они начинают описание, не название
STOP_WORDS = re.compile(
    r'[\s:–-]*(введите|выберите|укажите|нажмите|отображает|содержит'
    r'|показывает|заполняется|формируется|автоматически)\b.*',
    re.IGNORECASE,
)

# Мусор в начале строки: тире, двоеточия, номера рисунков
LEADING_JUNK  = re.compile(r'^[\s–\-:•·\d\.]+')
CAPTION_LABEL = re.compile(r'^Рис\.\s*\d+\s*[–—-]\s*', re.IGNORECASE)


def slugify(text: str) -> str:
    """Превратить текст подписи в имя файла."""
    text = LEADING_JUNK.sub('', text)
    text = STOP_WORDS.sub('', text)
    text = _translit(text).lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text[:40]


def find_caption(lines: list[str], img_idx: int) -> tuple[str, int | None]:
    """Найти подпись к изображению. Приоритет — строки с 'Рис. N —'.
    Возвращает (текст_подписи, индекс_строки_или_None)."""
    window = range(max(0, img_idx - 4), min(len(lines), img_idx + 5))

    for i in window:
        if i != img_idx and CAPTION_LABEL.match(lines[i].strip()):
            return CAPTION_LABEL.sub('', lines[i].strip()), i

    candidates = []
    for i in window:
        if i == img_idx:
            continue
        line = lines[i].strip()
        if not line or line.startswith('#') or line.startswith('!'):
            continue
        line = re.sub(r'\*+|_+|`', '', line)
        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
        if len(line) > 5:
            candidates.append((abs(i - img_idx), line))
    candidates.sort()
    return (candidates[0][1], None) if candidates else ('', None)


def apply_rename(old_abs: str, new_name: str, ext: str) -> str | None:
    """Переименовать файл. Возвращает новое имя или None при ошибке."""
    if not new_name.endswith(f'.{ext}'):
        new_name += f'.{ext}'
    new_abs = os.path.join(os.path.dirname(old_abs), new_name)
    if not os.path.exists(old_abs):
        print(f"  {YLW}файл не найден:{RST} {old_abs}")
        return None
    if os.path.exists(new_abs):
        print(f"  {RED}файл уже существует:{RST} {new_name}")
        return None
    shutil.move(old_abs, new_abs)
    return new_name


def ask_user(suggested: str) -> str | None:
    """Спросить подтверждение. Возвращает имя или None если пропустить."""
    print(f"  {DIM}[Enter] принять  [имя] своё  [s] пропустить  [Ctrl+C] выйти{RST}", end='  ')
    try:
        answer = input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    if answer.lower() == 's':
        print(f"  {YLW}пропущено{RST}")
        return None
    return answer if answer else suggested


def _handle_image(idx: int, line: str, lines: list, filepath: str,
                  dry_run: bool, auto: bool, strip_captions: bool,
                  renamed_map: dict, new_lines: list) -> int:
    """Обработать одну строку с изображением. Возвращает 1 если переименовано."""
    match = IMAGE_PATTERN.search(line)
    if not match:
        return 0
    img_path = match.group(2)
    img_file = os.path.basename(img_path)
    if not GENERIC_NAME.match(img_file):
        return 0

    ext = img_file.rsplit('.', 1)[-1].lower()
    old_abs = os.path.normpath(os.path.join(os.path.dirname(filepath), img_path))

    if img_file in renamed_map:
        new_name = renamed_map[img_file]
        new_lines[idx] = line.replace(img_path, img_path.replace(img_file, new_name))
        print(f"\n{BLD}{img_file}{RST}  {DIM}уже переименован →{RST} {new_name}")
        return 1

    caption, caption_idx = find_caption(lines, idx)
    suggested = (slugify(caption) + f'.{ext}') if caption else img_file
    print(f"\n{BLD}{img_file}{RST}")
    if caption:
        print(f"  {DIM}подпись:{RST} {caption[:80]}")
    print(f"  {CYN}→ предлагаю:{RST} {suggested}")

    if dry_run:
        return 0

    new_name = suggested if auto else ask_user(suggested)
    if new_name is None:
        return 0
    if auto:
        print(f"  {DIM}принято автоматически{RST}")

    result = apply_rename(old_abs, new_name, ext)
    if result:
        renamed_map[img_file] = result
        new_lines[idx] = line.replace(img_path, img_path.replace(img_file, result))
        if strip_captions and caption_idx is not None:
            new_lines[caption_idx] = None  # помечаем строку Рис. на удаление
        print(f"  {GRN}✓ переименован:{RST} {result}")
        return 1
    return 0


def process_file(filepath: str, dry_run: bool, auto: bool,
                 strip_captions: bool, renamed_map: dict) -> int:
    """Обработать один .md файл. renamed_map — глобальный кэш переименований."""
    with open(filepath, encoding='utf-8') as f:
        raw = f.read()
    lines = raw.splitlines()
    trailing_newline = raw.endswith('\n')
    new_lines: list = lines.copy()

    count = sum(
        _handle_image(idx, line, lines, filepath, dry_run, auto,
                      strip_captions, renamed_map, new_lines)
        for idx, line in enumerate(lines)
    )

    if count > 0 and not dry_run:
        content = '\n'.join(l for l in new_lines if l is not None)
        if trailing_newline:
            content += '\n'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n{GRN}✓ ссылки обновлены:{RST} {os.path.relpath(filepath)}")

    return count


def main() -> None:
    """Точка входа."""
    parser = argparse.ArgumentParser(
        description='rename_images — переименование скриншотов по подписям',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('paths', nargs='+', metavar='PATH',
                        help='Файлы .md или папки для обработки')
    parser.add_argument('--dry-run', action='store_true',
                        help='Показать предложения без изменения файлов')
    parser.add_argument('--auto', action='store_true',
                        help='Принять все предложения без вопросов')
    parser.add_argument('--strip-captions', action='store_true',
                        help='Удалять строки «Рис. N —» после переименования')
    args = parser.parse_args()

    files = []
    for path in args.paths:
        if os.path.isfile(path):
            files.append(path)
        else:
            files.extend(glob.glob(f"{path}/**/*.md", recursive=True))

    if not files:
        print(f"{YLW}Файлы не найдены{RST}")
        sys.exit(0)

    if args.dry_run:
        print(f"{DIM}Режим просмотра — файлы не изменяются{RST}\n")

    renamed_map: dict = {}  # img_file → new_name, общий для всех файлов
    total = 0

    for filepath in sorted(files):
        print(f"\n{BLD}── {os.path.relpath(filepath)}{RST}")
        total += process_file(filepath, dry_run=args.dry_run, auto=args.auto,
                              strip_captions=args.strip_captions,
                              renamed_map=renamed_map)

    label = 'Найдено' if args.dry_run else 'Переименовано'
    print(f"\n{label}: {total} скриншотов\n")


if __name__ == '__main__':
    main()
