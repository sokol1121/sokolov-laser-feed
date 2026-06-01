"""Работа с Google Таблицами через сервисный аккаунт.

Аутентификация: переменная GOOGLE_SERVICE_ACCOUNT_JSON (содержимое
service-account JSON целиком — удобно для GitHub Secrets) или путь к файлу в
GOOGLE_APPLICATION_CREDENTIALS.
"""
import json
import os


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Колонки ленты Tilda (импорт ленты из Google Таблиц). Порядок важен.
FEED_COLUMNS = [
    "Post ID",
    "Alias",
    "Title",
    "Category",
    "Media Type",
    "Media",
    "Description",
    "Text",
    "Date",
    "Visibility",
    "Thumb Image",
    "SEO Title",
    "SEO Description",
    "SEO Keywords",
    "Social Image",
]


def get_client():
    """Создаёт авторизованный клиент gspread из сервисного аккаунта."""
    import gspread
    from google.oauth2.service_account import Credentials

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    else:
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not path:
            raise RuntimeError(
                "Задай GOOGLE_SERVICE_ACCOUNT_JSON (содержимое JSON) "
                "или GOOGLE_APPLICATION_CREDENTIALS (путь к файлу)."
            )
        creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def open_ws(client, spreadsheet_id: str, sheet_name: str):
    """Открывает лист по id документа и имени листа (или первый лист)."""
    if not spreadsheet_id:
        raise RuntimeError("Не задан id Google Таблицы.")
    book = client.open_by_key(spreadsheet_id)
    return book.worksheet(sheet_name) if sheet_name else book.sheet1


def get_pending_topics(ws) -> list[dict]:
    """Темы без отметки в колонке status — те, что ещё не сгенерированы.

    Распознаёт колонки по заголовкам (рус/англ): topic/тема,
    keywords/ключевые слова, platform/платформа, status/статус.
    """
    values = ws.get_all_values()
    if not values:
        return []
    header = [h.strip().lower() for h in values[0]]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        return -1

    ti = col("topic", "тема")
    ki = col("keywords", "ключевые слова")
    pi = col("platform", "платформа")
    si = col("status", "статус")

    def cell(row, i):
        return row[i].strip() if 0 <= i < len(row) else ""

    pending = []
    for row_idx, row in enumerate(values[1:], start=2):
        topic = cell(row, ti)
        if not topic or cell(row, si):
            continue
        pending.append({
            "topic": topic,
            "keywords": cell(row, ki),
            "platform": cell(row, pi),
            "_row": row_idx,
            "_status_col": si,
        })
    return pending


def mark_topic_done(ws, topic: dict, date: str) -> None:
    """Ставит отметку в колонке status, чтобы тема не бралась повторно."""
    status_col = topic.get("_status_col", -1)
    if status_col is None or status_col < 0:
        return
    ws.update_cell(topic["_row"], status_col + 1, f"done {date}")


def ensure_feed_header(ws) -> None:
    """Если лист пуст — пишет строку заголовков ленты Tilda."""
    values = ws.get_all_values()
    if not values or not any(values[0]):
        ws.update("A1", [FEED_COLUMNS])


def get_feed_records(ws) -> list[dict]:
    """Все строки ленты как список словарей по заголовкам."""
    return ws.get_all_records()


def append_feed_row(ws, row: dict) -> None:
    """Дописывает строку статьи в конец ленты."""
    ws.append_row(
        [row.get(c, "") for c in FEED_COLUMNS],
        value_input_option="RAW",
    )
