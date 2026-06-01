"""Конфигурация из переменных окружения.

Все значения берутся из env, чтобы один и тот же код работал и локально
(через .env / экспорт), и в GitHub Actions (через secrets и variables).
"""
import os


# --- Claude API ---
# Ключ читается SDK автоматически из ANTHROPIC_API_KEY.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
# Глубина рассуждений модели: low | medium | high | max.
CLAUDE_EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")
# Потолок токенов на ответ (статья + JSON-поля). Стримим, поэтому можно щедро.
CLAUDE_MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "20000"))

# --- Источник тем (Google Таблица) ---
TOPICS_SPREADSHEET_ID = os.environ.get("TOPICS_SPREADSHEET_ID", "")
TOPICS_SHEET_NAME = os.environ.get("TOPICS_SHEET_NAME", "")

# --- Лента Tilda / архив опубликованных (Google Таблица) ---
FEED_SPREADSHEET_ID = os.environ.get("FEED_SPREADSHEET_ID", "")
FEED_SHEET_NAME = os.environ.get("FEED_SHEET_NAME", "")

# --- Сайт ---
SITE_URL = os.environ.get("SITE_URL", "https://sokolov-laser.ru")
CLINIC_NAME = os.environ.get("CLINIC_NAME", "Sokolov Laser")
DEFAULT_CATEGORY = os.environ.get("DEFAULT_CATEGORY", "Удаление тату и татуажа")
# Шаблон ссылки на статью для RSS. {site} и {slug} подставляются.
ARTICLE_URL_TEMPLATE = os.environ.get(
    "ARTICLE_URL_TEMPLATE", "{site}/article/{slug}"
)

# --- Параметры запуска ---
MAX_ARTICLES_PER_RUN = int(os.environ.get("MAX_ARTICLES_PER_RUN", "3"))

# --- Выходные файлы ---
ZEN_FEED_FILE = os.environ.get("ZEN_FEED_FILE", "feeds/zen.xml")
