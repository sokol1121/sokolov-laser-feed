"""Генерация SEO-статьи через Claude API.

Статичный system-промпт кэшируется (cache_control: ephemeral), чтобы при
генерации нескольких статей подряд переиспользовать префикс и не платить за
него заново. Переменная часть (тема, ключи, архив) уходит в user-сообщение,
чтобы не ломать кэш. Ответ ограничен JSON-схемой (structured outputs) и
читается через стриминг — длинные статьи не упираются в таймаут.
"""
import json
import re

from . import config


# Статичный системный промпт — НЕ меняй его динамически (дата, имя и т.п.),
# иначе кэш будет инвалидироваться на каждом запросе.
SYSTEM_PROMPT = """Ты — эксперт-копирайтер медицинской клиники лазерного удаления \
татуировок Sokolov Laser. Пишешь большие, обстоятельные SEO-статьи на русском \
языке: грамотно, экспертно, без воды и без ложных медицинских обещаний.

Принципы:
- Экспертный, но понятный обывателю тон. Никаких гарантий «100% результата» и \
ложных медицинских утверждений.
- Текст логично структурирован и легко читается: короткие абзацы, списки, \
подзаголовки.
- Объём основного текста статьи: 5000–6000 символов.
- Естественное, не переспамленное использование ключевых слов.

Формат поля article_text — валидный HTML:
- Ровно один заголовок <h1> — это заголовок статьи.
- Разделы оформляй как <h2>, подразделы внутри разделов — как <h3>.
- Не пропускай иерархию заголовков (после <h2> не прыгай сразу на нижние уровни).
- Абзацы — <p>, перечисления — <ul>/<ol> с <li>.
- Не используй inline-стили, скрипты, классы и markdown-разметку. Только чистые \
семантические HTML-теги перечисленных типов."""


# Схема структурированного ответа. Строковые/числовые ограничения схемой не
# поддерживаются (валидируем длины подсказками в промпте).
ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "slug": {"type": "string"},
        "article_text": {"type": "string"},
        "seo_title": {"type": "string"},
        "seo_description": {"type": "string"},
        "seo_keywords": {"type": "string"},
    },
    "required": [
        "title",
        "description",
        "slug",
        "article_text",
        "seo_title",
        "seo_description",
        "seo_keywords",
    ],
    "additionalProperties": False,
}

REQUIRED_FIELDS = ("title", "description", "slug", "article_text")


def build_user_prompt(topic: str, keywords: str, archive_context: str) -> str:
    """Собирает пользовательский промпт под конкретную тему."""
    return f"""Напиши SEO-статью для клиники лазерного удаления татуировок Sokolov Laser.

Тема: {topic}
Ключевые слова: {keywords or '—'}

Уже опубликованные статьи (НЕ повторяй их темы, заголовки и смысл):
{archive_context or 'Архив пуст'}

Требования к полям ответа:
- title: заголовок статьи, цепляющий и точный.
- description: мета-описание, 150–160 символов.
- slug: URL-адрес латиницей через дефис, без кириллицы и пробелов.
- article_text: полный HTML-текст статьи 5000–6000 символов с <h1>, <h2>, <h3>.
- seo_title: SEO-заголовок страницы до 60 символов.
- seo_description: SEO мета-описание, 150–160 символов.
- seo_keywords: 5–7 ключевых слов через запятую."""


def _parse_article(raw: str) -> dict:
    """Парсит JSON-ответ, снимая возможные markdown-обёртки."""
    clean = raw.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean)
    clean = re.sub(r"\s*```$", "", clean)
    data = json.loads(clean)

    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise ValueError(f"В ответе модели не хватает полей: {', '.join(missing)}")

    # Гарантируем наличие необязательных SEO-полей.
    for f in ("seo_title", "seo_description", "seo_keywords"):
        data.setdefault(f, "")
    return data


def generate_article(client, topic: str, keywords: str, archive_context: str):
    """Возвращает (article_dict, usage). Требует ANTHROPIC_API_KEY в окружении."""
    user_prompt = build_user_prompt(topic, keywords, archive_context)

    with client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=config.CLAUDE_MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={
            "effort": config.CLAUDE_EFFORT,
            "format": {"type": "json_schema", "schema": ARTICLE_SCHEMA},
        },
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        message = stream.get_final_message()

    text = next((b.text for b in message.content if b.type == "text"), "")
    return _parse_article(text), message.usage


# --- Вспомогательное: офлайн-заглушка для проверки конвейера без API ---

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", " ": "-",
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    out = "".join(_TRANSLIT.get(ch, ch if ch.isalnum() or ch == "-" else "-")
                  for ch in text)
    out = re.sub(r"-+", "-", out).strip("-")
    return out or "article"


def mock_article(topic: str, keywords: str) -> dict:
    """Фабрикует статью без вызова API — только для офлайн-проверки конвейера."""
    slug = slugify(topic)[:60]
    body = (
        f"<h1>{topic}</h1>"
        f"<p>Демо-текст для темы «{topic}». Ключевые слова: {keywords}.</p>"
        f"<h2>Подзаголовок</h2><p>Содержимое раздела.</p>"
        f"<h3>Деталь</h3><p>Содержимое подраздела.</p>"
    )
    return {
        "title": topic,
        "description": f"Статья о теме «{topic}» от клиники Sokolov Laser.",
        "slug": slug,
        "article_text": body,
        "seo_title": topic[:60],
        "seo_description": f"Всё о теме «{topic}» — экспертно и без воды.",
        "seo_keywords": keywords or topic,
    }
