# Telegram FAQ Bot MVP

Telegram-бот с видеоответами для обучения студентов инвестициям.

## Технологии

- Python 3.11
- aiogram 3.3
- FastAPI
- PostgreSQL 15
- Docker & Docker Compose
- SQLAlchemy (async)

## Структура проекта

```
telegram-faq-bot/
├── bot/              # Telegram бот
├── api/              # FastAPI backend
├── videos/           # Видеофайлы
├── init_db/          # SQL скрипты инициализации
└── docker-compose.yml
```

## Быстрый старт (локально)

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd telegram-faq-bot
```

### 2. Создать .env файл

```bash
cp .env.example .env
```

Заполнить `.env` файл:

- `BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
- `POSTGRES_PASSWORD` — придумать надёжный пароль
- Остальные параметры можно оставить по умолчанию

### 3. Добавить видеофайлы

Поместить `.mp4` файлы в папку `videos/`:

- `stocks_intro.mp4`
- `bonds_intro.mp4`
- `broker_account.mp4`
- `diversification.mp4`
- `financial_reports.mp4`

**ВАЖНО:** названия файлов должны совпадать с `video_url` в таблице `faq`.

### 4. Запустить проект

```bash
docker-compose up --build
```

Первый запуск займёт несколько минут (скачивание образов, сборка).

### 5. Проверить работу

- Откройте Telegram и найдите своего бота
- Отправьте `/start`
- Выберите категорию и вопрос
- Получите текстовый ответ и видео

### 6. Проверить API

Откройте в браузере: [http://localhost:8000/docs](http://localhost:8000/docs)

## API Endpoints

- `GET /` — health check
- `GET /faq/categories` — список категорий
- `GET /faq/category/{category}` — вопросы из категории
- `GET /faq/{faq_id}` — конкретный FAQ
- `GET /videos/{filename}` — статичные видеофайлы

## База данных

### Таблицы

**faq**

- Хранит вопросы, ответы и ссылки на видео

**logs**

- Логирует все действия пользователей

### Подключение к БД (для отладки)

```bash
docker exec -it faq_postgres psql -U faq_user -d faq_db
```

SQL запросы:

```sql
-- Посмотреть все FAQ
SELECT * FROM faq;

-- Посмотреть логи
SELECT * FROM logs ORDER BY created_at DESC LIMIT 10;

-- Статистика по пользователям
SELECT telegram_id, COUNT(*) as requests
FROM logs
GROUP BY telegram_id
ORDER BY requests DESC;
```

## Остановка проекта

```bash
docker-compose down
```

Удалить все данные (включая БД):

```bash
docker-compose down -v
```

## Деплой на VPS

### 1. Настроить сервер

```bash
# Установить Docker и Docker Compose на сервере
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Клонировать проект
git clone <repo-url>
cd telegram-faq-bot
```

### 2. Настроить .env для продакшена

```env
POSTGRES_PASSWORD=<сильный_пароль>
BOT_TOKEN=<токен_бота>
VIDEO_BASE_URL=https://your-domain.com
API_BASE_URL=http://api:8000

# Опционально: включить webhook
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-domain.com
WEBHOOK_PATH=/webhook
```

### 3. Настроить Nginx (опционально)

Для раздачи видео через домен нужен reverse proxy.

### 4. Запустить

```bash
docker-compose up -d
```

### 5. Проверить логи

```bash
docker-compose logs -f bot
docker-compose logs -f api
```

## Добавление новых FAQ

### Вариант 1: Через SQL

```sql
INSERT INTO faq (question, answer_text, video_url, category)
VALUES (
    'Что такое ETF?',
    'ETF — это биржевой инвестиционный фонд...',
    'etf_intro.mp4',
    'basics'
);
```

### Вариант 2: Через API (TODO)

Можно добавить admin endpoint для управления FAQ.

## Troubleshooting

### Бот не отвечает

- Проверить логи: `docker-compose logs bot`
- Проверить токен в .env
- Убедиться, что контейнеры запущены: `docker-compose ps`

### Видео не отправляются

- Проверить наличие файлов в `videos/`
- Проверить `VIDEO_BASE_URL` в .env
- Проверить логи API: `docker-compose logs api`

### Ошибки БД

- Проверить, что PostgreSQL запустился: `docker-compose ps`
- Проверить логи: `docker-compose logs postgres`
- Пересоздать БД: `docker-compose down -v && docker-compose up`

## Лицензия

MIT

```

---

## 22. videos/.gitkeep
```

# Эта папка для хранения видеофайлов

# Добавьте сюда .mp4 файлы согласно названиям из БД
