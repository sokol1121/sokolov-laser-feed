"""Оркестратор: темы -> генерация -> лента Tilda + RSS Дзена.

Запуск:
  python -m scripts.run                 # боевой режим (Google Sheets + Claude)
  python -m scripts.run --dry-run       # локально: темы из CSV, лента в CSV
  python -m scripts.run --dry-run --mock  # то же, но без вызова Claude API
"""
import argparse
import csv
import datetime
import os
import secrets

from . import config, generate, rss, sheets


def _today() -> str:
    return datetime.datetime.now().strftime("%d.%m.%Y")


def _post_id() -> str:
    return secrets.token_hex(5)  # 10 hex-символов, как Math.random().toString(36)


def article_to_feed_row(article: dict) -> dict:
    """Раскладывает статью по колонкам ленты Tilda."""
    return {
        "Post ID": _post_id(),
        "Alias": article["slug"],
        "Title": article["title"],
        "Category": config.DEFAULT_CATEGORY,
        "Media Type": "article",
        "Media": "image",
        "Description": article["description"],
        "Text": article["article_text"],
        "Date": _today(),
        "Visibility": "SHOW",
        "Thumb Image": article.get("thumb_image", ""),
        "SEO Title": article["seo_title"],
        "SEO Description": article["seo_description"],
        "SEO Keywords": article["seo_keywords"],
        "Social Image": "",
    }


def build_archive_context(records: list[dict], limit: int = 60) -> str:
    """Строит список уже опубликованных статей, чтобы не повторяться."""
    lines = []
    for r in records[-limit:]:
        title = r.get("Title") or ""
        slug = r.get("Alias") or ""
        kw = r.get("SEO Keywords") or ""
        line = f"- {title} | slug: {slug} | kw: {kw}"
        if len(line) > 10:
            lines.append(line)
    return "\n".join(lines) if lines else "Архив пуст"


class SheetsBackend:
    """Боевой бэкенд: темы и лента в Google Таблицах."""

    def __init__(self):
        gc = sheets.get_client()
        self.topics_ws = sheets.open_ws(
            gc, config.TOPICS_SPREADSHEET_ID, config.TOPICS_SHEET_NAME
        )
        self.feed_ws = sheets.open_ws(
            gc, config.FEED_SPREADSHEET_ID, config.FEED_SHEET_NAME
        )
        sheets.ensure_feed_header(self.feed_ws)

    def pending_topics(self):
        return sheets.get_pending_topics(self.topics_ws)

    def feed_records(self):
        return sheets.get_feed_records(self.feed_ws)

    def append(self, row):
        sheets.append_feed_row(self.feed_ws, row)

    def mark_done(self, topic):
        sheets.mark_topic_done(self.topics_ws, topic, _today())


class LocalBackend:
    """Локальный бэкенд для --dry-run: темы и лента в CSV-файлах."""

    def __init__(self, topics_csv: str, feed_csv: str):
        self.topics_csv = topics_csv
        self.feed_csv = feed_csv

    def pending_topics(self):
        if not os.path.exists(self.topics_csv):
            return []
        out = []
        with open(self.topics_csv, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=2):
                topic = (row.get("topic") or row.get("тема") or "").strip()
                if not topic or (row.get("status") or "").strip():
                    continue
                out.append({
                    "topic": topic,
                    "keywords": (row.get("keywords") or "").strip(),
                    "platform": (row.get("platform") or "").strip(),
                    "_row": i,
                })
        return out

    def feed_records(self):
        if not os.path.exists(self.feed_csv):
            return []
        with open(self.feed_csv, encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def append(self, row):
        os.makedirs(os.path.dirname(self.feed_csv) or ".", exist_ok=True)
        exists = os.path.exists(self.feed_csv)
        with open(self.feed_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sheets.FEED_COLUMNS)
            if not exists:
                writer.writeheader()
            writer.writerow({c: row.get(c, "") for c in sheets.FEED_COLUMNS})

    def mark_done(self, topic):
        pass  # в локальном режиме статусы не трогаем


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="локально: темы и лента в CSV, без Google Sheets")
    parser.add_argument("--mock", action="store_true",
                        help="не вызывать Claude API (заглушка статьи)")
    parser.add_argument("--max", type=int, default=config.MAX_ARTICLES_PER_RUN,
                        help="максимум статей за запуск")
    parser.add_argument("--topics-csv", default="topics.sample.csv")
    parser.add_argument("--feed-csv", default="feeds/feed.csv")
    args = parser.parse_args()

    backend = (
        LocalBackend(args.topics_csv, args.feed_csv)
        if args.dry_run
        else SheetsBackend()
    )

    pending = backend.pending_topics()[: args.max]
    archive = build_archive_context(backend.feed_records())

    client = None
    if not args.mock:
        import anthropic  # ленивый импорт: --mock работает без пакета
        client = anthropic.Anthropic()  # ключ из ANTHROPIC_API_KEY

    generated = 0
    for topic in pending:
        print(f"→ Генерация: {topic['topic']}")
        if args.mock:
            article = generate.mock_article(topic["topic"], topic["keywords"])
        else:
            article, usage = generate.generate_article(
                client, topic["topic"], topic["keywords"], archive
            )
            cache_read = getattr(usage, "cache_read_input_tokens", 0)
            print(f"   токены вход/выход: {usage.input_tokens}/"
                  f"{usage.output_tokens} (из кэша {cache_read})")

        backend.append(article_to_feed_row(article))
        backend.mark_done(topic)
        # Пополняем архив, чтобы следующая тема в этом же запуске не дублировалась.
        archive += (f"\n- {article['title']} | slug: {article['slug']} "
                    f"| kw: {article['seo_keywords']}")
        generated += 1

    # Пересобираем RSS Дзена из всей ленты (полная проекция таблицы).
    records = backend.feed_records()
    rss.write_feed(records, config.ZEN_FEED_FILE)

    print(f"Готово. Сгенерировано статей: {generated}. "
          f"RSS: {config.ZEN_FEED_FILE} ({len(records)} записей)")


if __name__ == "__main__":
    main()
