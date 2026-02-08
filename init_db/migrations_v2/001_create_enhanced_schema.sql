-- ============================================
-- MIGRATION v2: Enhanced Schema
-- ============================================

-- 1. Основная таблица FAQ (улучшенная)
CREATE TABLE IF NOT EXISTS faq_v2 (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0
);

-- 2. Контент FAQ (разделение языков)
CREATE TABLE IF NOT EXISTS faq_content (
    id SERIAL PRIMARY KEY,
    faq_id INTEGER REFERENCES faq_v2(id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL,
    question TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    video_url TEXT,

-- Enrichment данные
question_normalized TEXT, question_keywords TEXT[],

-- Embeddings
question_embedding vector(1536),
    answer_embedding vector(1536),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(faq_id, language)
);

-- 3. Таблица синонимов
CREATE TABLE IF NOT EXISTS synonyms (
    id SERIAL PRIMARY KEY,
    language VARCHAR(10) NOT NULL,
    term TEXT NOT NULL,
    synonyms TEXT[] NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Таблица тегов
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS faq_tags (
    faq_id INTEGER REFERENCES faq_v2 (id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (faq_id, tag_id)
);

-- 5. Кеш поисковых запросов
CREATE TABLE IF NOT EXISTS search_cache (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64) UNIQUE NOT NULL,
    language VARCHAR(10) NOT NULL,
    query_normalized TEXT NOT NULL,
    faq_results JSONB NOT NULL,
    hit_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Аналитика запросов
CREATE TABLE IF NOT EXISTS query_analytics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    query_original TEXT NOT NULL,
    query_normalized TEXT NOT NULL,
    language VARCHAR(10),
    detected_intent VARCHAR(50),
    top_faq_id INTEGER REFERENCES faq_v2 (id),
    top_score FLOAT,
    results_count INTEGER,
    user_clicked_faq_id INTEGER REFERENCES faq_v2 (id),
    user_satisfied BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Индексы
CREATE INDEX IF NOT EXISTS idx_faq_content_lang ON faq_content (language);

CREATE INDEX IF NOT EXISTS idx_faq_content_faq_id ON faq_content (faq_id);

CREATE INDEX IF NOT EXISTS idx_faq_content_keywords ON faq_content USING GIN (question_keywords);

-- pgvector индексы HNSW
CREATE INDEX IF NOT EXISTS idx_faq_question_embedding ON faq_content USING hnsw (
    question_embedding vector_cosine_ops
)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_faq_answer_embedding ON faq_content USING hnsw (
    answer_embedding vector_cosine_ops
)
WITH (m = 16, ef_construction = 64);

-- Индексы для кеша
CREATE INDEX IF NOT EXISTS idx_search_cache_hash ON search_cache (query_hash);

CREATE INDEX IF NOT EXISTS idx_search_cache_last_used ON search_cache (last_used_at DESC);

-- Индексы для аналитики
CREATE INDEX IF NOT EXISTS idx_query_analytics_created ON query_analytics (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_analytics_user ON query_analytics (user_id, created_at DESC);

-- 8. Триггер для updated_at
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

-- 9. Миграция данных из старой схемы
INSERT INTO
    faq_v2 (id, category, created_at)
SELECT id, category, created_at
FROM faq ON CONFLICT (id) DO NOTHING;

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
FROM faq ON CONFLICT (faq_id, language) DO NOTHING;

-- 10. Нормализация вопросов
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
    )
WHERE
    question_normalized IS NULL;

UPDATE faq_content
SET
    question_keywords = array_remove (question_keywords, '');

-- 11. Добавление синонимов
INSERT INTO synonyms (language, term, synonyms) VALUES
('kk', 'облигация', ARRAY['бонд', 'облиг', 'облигациялар', 'қарыз құжаты']),
('kk', 'акция', ARRAY['акциялар', 'үлес', 'қор']),
('kk', 'шот', ARRAY['счет', 'аккаунт', 'есепшот']),
('ru', 'облигация', ARRAY['бонд', 'облиг', 'облигации', 'долговая бумага']),
('ru', 'акция', ARRAY['акции', 'доля', 'equity', 'stock']),
('ru', 'счет', ARRAY['аккаунт', 'account'])
ON CONFLICT DO NOTHING;

-- Вывод статистики
DO $$
DECLARE
    faq_v2_count INTEGER;
    content_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO faq_v2_count FROM faq_v2;
    SELECT COUNT(*) INTO content_count FROM faq_content;
    
    RAISE NOTICE '✅ Enhanced schema migration complete!';
    RAISE NOTICE '📊 FAQ v2 records: %', faq_v2_count;
    RAISE NOTICE '📝 FAQ content records: %', content_count;
END $$;