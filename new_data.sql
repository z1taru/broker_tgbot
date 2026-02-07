-- ============================================
-- НОВАЯ PRODUCTION СХЕМА
-- ============================================

-- 1. Основная таблица FAQ (улучшенная)
CREATE TABLE faq_v2 (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0, -- для ранжирования
    view_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0
);

-- 2. Контент FAQ (разделение языков)
CREATE TABLE faq_content (
    id SERIAL PRIMARY KEY,
    faq_id INTEGER REFERENCES faq_v2(id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL,
    question TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    video_url TEXT,

-- Enrichment данные
question_normalized TEXT, -- lowercase, без пунктуации
    question_keywords TEXT[], -- ключевые слова

-- Embeddings
question_embedding vector (1536), answer_embedding vector (1536),

-- Метаданные
created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(faq_id, language) );

-- 3. Таблица синонимов для улучшения поиска
CREATE TABLE synonyms (
    id SERIAL PRIMARY KEY,
    language VARCHAR(10) NOT NULL,
    term TEXT NOT NULL,
    synonyms TEXT[] NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Примеры синонимов
INSERT INTO synonyms (language, term, synonyms) VALUES
('kk', 'облигация', ARRAY['бонд', 'облиг', 'облигациялар', 'қарыз құжаты']),
('kk', 'акция', ARRAY['акциялар', 'үлес', 'қор']),
('kk', 'шот', ARRAY['счет', 'аккаунт', 'есепшот']),
('ru', 'облигация', ARRAY['бонд', 'облиг', 'облигации', 'долговая бумага']),
('ru', 'акция', ARRAY['акции', 'доля', 'equity', 'stock']),
('ru', 'счет', ARRAY['аккаунт', 'account']);

-- 4. Таблица тегов
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(100)
);

CREATE TABLE faq_tags (
    faq_id INTEGER REFERENCES faq_v2 (id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (faq_id, tag_id)
);

-- 5. Кеширование поисковых запросов
CREATE TABLE search_cache (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64) UNIQUE NOT NULL, -- MD5 от нормализованного запроса
    language VARCHAR(10) NOT NULL,
    query_normalized TEXT NOT NULL,
    faq_results JSONB NOT NULL, -- [{faq_id, score, rank}]
    hit_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. История запросов для аналитики
CREATE TABLE query_analytics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    query_original TEXT NOT NULL,
    query_normalized TEXT NOT NULL,
    language VARCHAR(10),
    detected_intent VARCHAR(50),

-- Результаты поиска
top_faq_id INTEGER REFERENCES faq_v2 (id),
top_score FLOAT,
results_count INTEGER,

-- Действие пользователя
user_clicked_faq_id INTEGER REFERENCES faq_v2(id),
    user_satisfied BOOLEAN,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Индексы для performance
CREATE INDEX idx_faq_content_lang ON faq_content (language);

CREATE INDEX idx_faq_content_faq_id ON faq_content (faq_id);

CREATE INDEX idx_faq_content_keywords ON faq_content USING GIN (question_keywords);

-- pgvector индексы (HNSW быстрее чем IVFFlat для малых датасетов)
CREATE INDEX idx_faq_question_embedding ON faq_content USING hnsw (
    question_embedding vector_cosine_ops
)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_faq_answer_embedding ON faq_content USING hnsw (
    answer_embedding vector_cosine_ops
)
WITH (m = 16, ef_construction = 64);

-- Индексы для кеша
CREATE INDEX idx_search_cache_hash ON search_cache (query_hash);

CREATE INDEX idx_search_cache_last_used ON search_cache (last_used_at DESC);

-- Индексы для аналитики
CREATE INDEX idx_query_analytics_created ON query_analytics (created_at DESC);

CREATE INDEX idx_query_analytics_user ON query_analytics (user_id, created_at DESC);

-- 8. Функция автообновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER faq_v2_updated_at
    BEFORE UPDATE ON faq_v2
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- МИГРАЦИЯ ИЗ СТАРОЙ СХЕМЫ
-- ============================================

-- Шаг 1: Мигрировать основные FAQ
INSERT INTO
    faq_v2 (id, category, created_at)
SELECT id, category, created_at
FROM faq;

-- Шаг 2: Мигрировать контент
INSERT INTO
    faq_content (
        faq_id,
        language,
        question,
        answer_text,
        video_url,
        question_embedding
    )
SELECT
    id,
    language,
    question,
    answer_text,
    video_url,
    embedding
FROM faq;

-- Шаг 3: Нормализовать вопросы
UPDATE faq_content
SET
    question_normalized = LOWER(
        REGEXP_REPLACE(question, '[^\w\s]', '', 'g')
    ),
    question_keywords = string_to_array (
        LOWER(
            REGEXP_REPLACE(question, '[^\w\s]', ' ', 'g')
        ),
        ' '
    );

-- Шаг 4: Удалить пустые keywords
UPDATE faq_content
SET
    question_keywords = array_remove (question_keywords, '');