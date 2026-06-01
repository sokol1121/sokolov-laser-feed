"""Сборка RSS-фида для Яндекс Дзена из записей ленты.

Дзен импортирует RSS, где полный HTML статьи лежит в <content:encoded>.
Фид — чистая проекция ленты Tilda: пересобираем его целиком из всех записей,
чтобы он всегда был синхронен с таблицей.
"""
import datetime
import os
from xml.sax.saxutils import escape

from . import config


def _pubdate(date_str: str) -> str:
    """dd.MM.yyyy (или ISO) -> RFC-822, который ждёт RSS."""
    dt = None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime((date_str or "").strip(), fmt)
            break
        except (ValueError, TypeError):
            continue
    if dt is None:
        dt = datetime.datetime.now()
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _cdata(body: str) -> str:
    # Защита от закрытия CDATA внутри HTML.
    return (body or "").replace("]]>", "]]]]><![CDATA[>")


def build_rss(records: list[dict]) -> str:
    site = config.SITE_URL.rstrip("/")
    items = []
    for r in records:
        title = (r.get("Title") or "").strip()
        if not title:
            continue
        slug = (r.get("Alias") or "").strip()
        link = config.ARTICLE_URL_TEMPLATE.format(site=site, slug=slug)
        description = r.get("Description") or ""
        body = r.get("Text") or ""
        items.append(
            "    <item>\n"
            f"      <title>{escape(title)}</title>\n"
            f"      <link>{escape(link)}</link>\n"
            f'      <guid isPermaLink="false">{escape(slug or title)}</guid>\n'
            f"      <pubDate>{_pubdate(r.get('Date'))}</pubDate>\n"
            f"      <description>{escape(description)}</description>\n"
            f"      <content:encoded><![CDATA[{_cdata(body)}]]></content:encoded>\n"
            "    </item>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        "  <channel>\n"
        f"    <title>{escape(config.CLINIC_NAME)} — Блог</title>\n"
        f"    <link>{escape(config.SITE_URL)}</link>\n"
        "    <description>Статьи о лазерном удалении татуировок, "
        "косметологии и уходе за кожей</description>\n"
        "    <language>ru</language>\n"
        + ("\n".join(items) + "\n" if items else "")
        + "  </channel>\n"
        "</rss>\n"
    )


def write_feed(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_rss(records))
