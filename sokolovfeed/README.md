# sokolov-laser-feed

Автоматизация генерации SEO-статей для сайта **sokolov-laser.ru** (клиника
лазерного удаления татуировок). Повторяет прежнюю схему из n8n, но в виде
Python-скрипта, который запускается по расписанию через GitHub Actions.

## Как это работает

```
Темы (Google Таблица)
        │
        ▼
  Claude API (claude-opus-4-8) ──► JSON статьи (title, slug, article_text HTML, SEO…)
        │
        ├──► Лента Tilda  (Google Таблица «новые статьи») ──► импорт ленты в Tilda
        └──► RSS feeds/zen.xml (content:encoded) ──► импорт в Яндекс Дзен
```

1. **Темы.** Лист с колонками `topic` / `keywords` / `platform` / `status`
   (понимаются и русские заголовки: `тема`, `ключевые слова`, `платформа`,
   `статус`). Берутся строки с пустым `status`.
2. **Генерация.** Для каждой темы — запрос к Claude. Статичный системный промпт
   кэшируется (`cache_control`), переменная часть (тема, ключи, архив уже
   опубликованных статей — чтобы не повторяться) уходит в сообщение. Ответ
   ограничен JSON-схемой (structured outputs).
3. **Лента Tilda.** Готовая статья дописывается строкой в Google Таблицу в
   формате ленты Tilda (`Post ID`, `Alias`, `Title`, `Text`, `SEO Title` …).
   Tilda импортирует этот лист в раздел статей.
4. **RSS для Дзена.** Файл `feeds/zen.xml` целиком пересобирается из ленты и
   коммитится обратно — Дзен забирает его по ссылке (через GitHub Pages).
5. Тема помечается `done <дата>`, чтобы не сгенерироваться повторно.

## Структура

```
scripts/
  config.py     — настройки из переменных окружения
  generate.py   — промпт, JSON-схема, вызов Claude (+ офлайн-заглушка)
  sheets.py     — чтение тем и запись ленты в Google Sheets
  rss.py        — сборка RSS-фида для Дзена
  run.py        — оркестратор (точка входа)
.github/workflows/generate-articles.yml — запуск по расписанию
topics.sample.csv — пример тем для локального --dry-run
feeds/zen.xml     — RSS-фид (обновляется автоматически)
```

## Локальный запуск

```bash
pip install -r requirements.txt

# 1) Проверить конвейер без API и без Google Sheets (темы и лента в CSV):
python -m scripts.run --dry-run --mock

# 2) То же, но с реальной генерацией через Claude:
export ANTHROPIC_API_KEY=sk-ant-...
python -m scripts.run --dry-run

# 3) Боевой режим (Google Sheets + Claude): заполни .env по .env.example
set -a; . ./.env; set +a
python -m scripts.run
```

Флаги: `--max N` (сколько статей за запуск), `--topics-csv`, `--feed-csv`.

## Настройка GitHub Actions

В репозитории **Settings → Secrets and variables → Actions**:

**Secrets:**
- `ANTHROPIC_API_KEY` — ключ Claude API
- `GOOGLE_SERVICE_ACCOUNT_JSON` — содержимое JSON сервисного аккаунта Google
- `TOPICS_SPREADSHEET_ID`, `FEED_SPREADSHEET_ID` — id Google Таблиц

**Variables:**
- `TOPICS_SHEET_NAME`, `FEED_SHEET_NAME` — имена листов
- `SITE_URL`, `DEFAULT_CATEGORY` — необязательно

Дай сервисному аккаунту доступ (редактор) к обеим таблицам — поделись ими на
email вида `...@...iam.gserviceaccount.com`.

Workflow запускается по расписанию (понедельник 06:00 UTC) или вручную через
**Actions → Generate Articles → Run workflow**.

## Публикация фида

- **Яндекс Дзен:** включи GitHub Pages для репозитория и дай Дзену ссылку
  `https://<user>.github.io/sokolov-laser-feed/feeds/zen.xml`.
- **Tilda:** в настройках ленты укажи импорт из той Google Таблицы, куда
  скрипт дописывает строки (`FEED_SPREADSHEET_ID` / `FEED_SHEET_NAME`).

> `fixed_feed_yml.xml` — отдельный YML-каталог услуг клиники, к этой
> автоматизации статей не относится.
