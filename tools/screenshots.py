#!/usr/bin/env python3
"""
screenshots — автоматические скриншоты документации через Selenium.

Открывает страницы приложения в браузере, делает скриншоты и сохраняет
в папку media/ с читаемыми именами файлов. После сохранения сжимает PNG.

Использование:
  python3 tools/screenshots.py                     # снять все скриншоты
  python3 tools/screenshots.py --page payment_order  # один конкретный экран
  python3 tools/screenshots.py --list              # список всех экранов
  python3 tools/screenshots.py --config my.toml   # другой конфиг

Требования:
  pip install selenium
  ChromeDriver: https://chromedriver.chromium.org/
"""

import os
import sys
import argparse
import subprocess

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        print("Требуется Python 3.11+ или: pip install tomli")
        sys.exit(1)

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("Установи Selenium: pip install selenium")
    sys.exit(1)

# ── Цвета ──────────────────────────────────────────────────────────────────────
GRN = "\033[32m"
RED = "\033[31m"
YLW = "\033[33m"
DIM = "\033[2m"
RST = "\033[0m"


# ── Загрузка конфига ───────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    """Загрузить конфиг из TOML-файла."""
    if not os.path.exists(path):
        print(f"{RED}Конфиг не найден:{RST} {path}")
        sys.exit(1)
    with open(path, "rb") as f:
        return tomllib.load(f)


# ── Браузер ────────────────────────────────────────────────────────────────────

def create_driver(window: dict) -> webdriver.Chrome:
    """Создать и настроить экземпляр браузера Chrome."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")           # без GUI
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"--window-size={window['width']},{window['height']}")
    return webdriver.Chrome(options=options)


def login(driver: webdriver.Chrome, config: dict) -> None:
    """Авторизоваться в приложении."""
    login_cfg = config["login"]
    base_url = config["project"]["base_url"]

    driver.get(base_url + login_cfg["url"])

    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.NAME, login_cfg["username_field"])))

    driver.find_element(By.NAME, login_cfg["username_field"]).send_keys(login_cfg["username"])
    driver.find_element(By.NAME, login_cfg["password_field"]).send_keys(login_cfg["password"])
    driver.find_element(By.CSS_SELECTOR, login_cfg["submit_selector"]).click()

    wait.until(EC.url_contains(login_cfg.get("success_url", "/")))
    print(f"  {GRN}✓ Авторизация успешна{RST}")


# ── Скриншоты ──────────────────────────────────────────────────────────────────

def take_screenshot(driver: webdriver.Chrome, page: dict, output_dir: str, base_url: str) -> str:
    """Открыть страницу и сохранить скриншот."""
    url = base_url + page["url"]
    driver.get(url)

    # Ждём загрузки если указан селектор
    if "wait_for" in page:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, page["wait_for"]))
        )

    # Дополнительная пауза если нужна (для анимаций)
    if "delay" in page:
        import time
        time.sleep(page["delay"])

    filepath = os.path.join(output_dir, page["file"])
    driver.save_screenshot(filepath)
    return filepath


def compress(filepath: str) -> None:
    """Сжать PNG через oxipng если установлен."""
    if subprocess.run(["which", "oxipng"], capture_output=True).returncode == 0:
        subprocess.run(["oxipng", "-o", "4", "--strip", "safe", "--quiet", filepath])


# ── Точка входа ────────────────────────────────────────────────────────────────

def main() -> None:
    """Точка входа: разобрать аргументы и запустить съёмку скриншотов."""
    parser = argparse.ArgumentParser(
        description="screenshots — автоматические скриншоты через Selenium",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config", default="screenshots.toml", metavar="FILE")
    parser.add_argument("--page", metavar="ID", help="Снять только один экран по id")
    parser.add_argument("--list", action="store_true", help="Показать список экранов")
    args = parser.parse_args()

    config = load_config(args.config)
    project = config["project"]
    pages = config.get("pages", [])
    output_dir = project.get("output_dir", "docs/user-guide/media")

    if args.list:
        print(f"\n{len(pages)} экранов в конфиге:\n")
        for p in pages:
            print(f"  {DIM}{p['id']:30}{RST} {p['description']}")
        print()
        return

    if args.page:
        pages = [p for p in pages if p["id"] == args.page]
        if not pages:
            print(f"{RED}Экран не найден:{RST} {args.page}")
            sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print(f"\n→ Запуск браузера...")
    driver = create_driver(project.get("window", {"width": 1280, "height": 900}))

    try:
        if "login" in config:
            login(driver, config)

        success = 0
        for page in pages:
            try:
                filepath = take_screenshot(driver, page, output_dir, project["base_url"])
                compress(filepath)
                print(f"  {GRN}✓{RST} {page['description']} → {page['file']}")
                success += 1
            except Exception as e:
                print(f"  {RED}✗{RST} {page['description']}: {e}")
    finally:
        driver.quit()

    print(f"\n{GRN}Готово:{RST} {success}/{len(pages)} скриншотов сохранено в {output_dir}/\n")


if __name__ == "__main__":
    main()
