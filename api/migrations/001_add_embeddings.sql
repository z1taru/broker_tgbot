-- Add embedding column to faq table
ALTER TABLE faq ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create index for cosine similarity search
CREATE INDEX IF NOT EXISTS idx_faq_embedding ON faq USING ivfflat (embedding vector_cosine_ops);

-- Add comment
COMMENT ON COLUMN faq.embedding IS 'OpenAI text-embedding-3-small vector (1536 dimensions)';