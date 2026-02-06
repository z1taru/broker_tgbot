# 🤖 FAQ Bot - Инвестициялық Куратор

Telegram бот студенттер үшін инвестициялар туралы сұрақ-жауаптармен және видео түсініктемелермен.

## 🎯 Мүмкіндіктер

- ✅ FAQ жүйесі видео жауаптармен
- ✅ Қазақ тілінде толық интерфейс
- ✅ Категориялар бойынша навигация
- ✅ Production-ready архитектура
- ✅ Docker қолдауы
- ✅ Автоматты retry және fallback
- ✅ Толық логирование
- ✅ Health checks

## 🏗️ Архитектура

```
faq-bot/
├── api/              # FastAPI backend
│   └── app/
│       ├── api/      # Routes (endpoints)
│       ├── core/     # Database, logging, exceptions
│       ├── models/   # SQLAlchemy models
│       ├── repositories/ # Data access layer
│       ├── schemas/  # Pydantic schemas
│       └── services/ # Business logic
│
├── bot/              # Telegram bot
│   └── app/
│       ├── core/     # Database, logging
│       ├── handlers/ # Message/callback handlers
│       ├── keyboards/ # Inline keyboards
│       ├── middlewares/ # Logging middleware
│       └── services/ # API client, video service
│
├── init_db/          # Database initialization
├── videos/           # Video files
└── docker-compose.yml
```

## 🚀 Қалай жүктеп іске қосу

### 1. Репозиторийді клондау

```bash
git clone <your-repo-url>
cd faq-bot
```

### 2. Environment файлын жасау

```bash
cp .env.example .env
```

`.env` файлын толтырыңыз:

```env
# Database
POSTGRES_DB=faq_bot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# Bot
BOT_TOKEN=your_telegram_bot_token

# API
VIDEO_BASE_URL=http://localhost:8000
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### 3. Docker арқылы жүктеу

```bash
# Барлық сервистерді жүктеу
docker-compose up -d

# Логтарды көру
docker-compose logs -f

# Тоқтату
docker-compose down
```

### 4. Видео файлдарын қосу

Видео файлдарды `videos/` папкасына салыңыз:

```bash
videos/
├── tabys_pro_bonds.mp4
├── freedom_second_account.mp4
├── freedom_support.mp4
└── currency_exchange.mp4
```

## 🔧 Development режимі

### API-ді локальда жүктеу

```bash
cd api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/api/docs

### Ботты локальда жүктеу

```bash
cd bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## 📊 Database Schema

```sql
-- FAQ таблицасы
faq (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    video_url TEXT,
    category VARCHAR(100) NOT NULL,
    language VARCHAR(10) DEFAULT 'kk',
    created_at TIMESTAMP WITH TIME ZONE
)

-- Logs таблицасы
logs (
    id SERIAL PRIMARY KEY,
    telegram_id VARCHAR(100) NOT NULL,
    question TEXT,
    matched_faq_id INTEGER,
    confidence FLOAT,
    created_at TIMESTAMP WITH TIME ZONE
)
```

## 🎨 UX Мысалдар

### Приветствие

```
Сәлем, Арман! 👋

Мен – сенің инвестициялар бойынша AI-кураторыңмын! 🎯

Менде:
📊 Инвестиция туралы барлық сұрақтарға жауап бар
🎥 Әрбір жауапқа видео-түсініктеме қосылған
💡 Практикалық кеңестер мен нұсқаулар

Өзіңді қызықтыратын тақырыпты таңда – бірге үйренейік! 🚀
```

### Категориялар

- 📱 Tabys Pro
- 🏦 Freedom Broker
- 📚 Негіздер
- 🚀 Қайдан бастау

## 🔒 Production Deployment

### Environment variables

```env
ENVIRONMENT=production
LOG_LEVEL=WARNING
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

### Nginx конфигурациясы

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📝 API Endpoints

### FAQ

- `GET /faq/categories` - Категориялар тізімі
- `GET /faq/category/{category}` - Категория бойынша FAQ
- `GET /faq/{id}` - FAQ бір жазба
- `POST /faq/` - Жаңа FAQ жасау
- `PATCH /faq/{id}` - FAQ жаңарту
- `DELETE /faq/{id}` - FAQ өшіру

### Health

- `GET /health` - Health check

## 🧪 Testing

```bash
# API тестілеу
cd api
pytest

# Bot тестілеу
cd bot
pytest
```

## 📈 Monitoring

### Healthchecks

```bash
# API health
curl http://localhost:8000/health

# Database connection
docker-compose exec postgres pg_isready
```

### Logs

```bash
# Барлық логтар
docker-compose logs -f

# Бот логтары
docker-compose logs -f bot

# API логтары
docker-compose logs -f api
```

## 🛠️ Troubleshooting

### Бот жұмысістемейді

1. Token-ды тексеріңіз:

```bash
docker-compose logs bot | grep "BOT_TOKEN"
```

2. API қолжетімділігін тексеріңіз:

```bash
curl http://localhost:8000/health
```

### Видео жүктелмейді

1. `videos/` папкасын тексеріңіз
2. Файл аттарын БД-мен салыстырыңыз
3. Файл өлшемін тексеріңіз (max 50MB)

### Database қателері

```bash
# Database логтары
docker-compose logs postgres

# Қайта жүктеу
docker-compose restart postgres
```

## 📞 Қолдау

Сұрақтар болса:

- Issue ашыңыз GitHub-та
- Құжаттаманы оқыңыз

## 📄 License

MIT License

## 🎉 Алғыс

Бұл проект студенттерге инвестиция туралы білім беру үшін жасалды.
