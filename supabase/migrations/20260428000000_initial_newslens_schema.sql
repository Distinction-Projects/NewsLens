CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.import_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_mode TEXT NOT NULL DEFAULT 'current',
  snapshot_date DATE,
  source_url TEXT,
  schema_version TEXT,
  contract TEXT,
  generated_at TIMESTAMPTZ,
  digest_generated_at TIMESTAMPTZ,
  digest_run_id TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  article_count INTEGER NOT NULL DEFAULT 0,
  score_count INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS public.sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.feeds (
  id TEXT PRIMARY KEY,
  source_id TEXT REFERENCES public.sources(id) ON DELETE SET NULL,
  name TEXT,
  url TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.articles (
  id TEXT PRIMARY KEY,
  source_id TEXT REFERENCES public.sources(id) ON DELETE SET NULL,
  feed_id TEXT REFERENCES public.feeds(id) ON DELETE SET NULL,
  title TEXT,
  link TEXT,
  published_at TIMESTAMPTZ,
  summary TEXT,
  ai_summary TEXT,
  scrape_error TEXT,
  scraped_ok BOOLEAN NOT NULL DEFAULT TRUE,
  score_value DOUBLE PRECISION,
  score_max_value DOUBLE PRECISION,
  score_percent DOUBLE PRECISION,
  rubric_count INTEGER,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_seen_import_run_id UUID REFERENCES public.import_runs(id) ON DELETE SET NULL,
  last_seen_import_run_id UUID REFERENCES public.import_runs(id) ON DELETE SET NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.article_tags (
  article_id TEXT NOT NULL REFERENCES public.articles(id) ON DELETE CASCADE,
  tag_type TEXT NOT NULL CHECK (tag_type IN ('ai', 'topic')),
  tag TEXT NOT NULL,
  tag_normalized TEXT NOT NULL,
  PRIMARY KEY (article_id, tag_type, tag_normalized)
);

CREATE TABLE IF NOT EXISTS public.lenses (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.rubrics (
  id TEXT PRIMARY KEY,
  lens_id TEXT REFERENCES public.lenses(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  signature TEXT NOT NULL UNIQUE,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.article_scores (
  article_id TEXT NOT NULL REFERENCES public.articles(id) ON DELETE CASCADE,
  lens_id TEXT NOT NULL REFERENCES public.lenses(id) ON DELETE CASCADE,
  rubric_id TEXT REFERENCES public.rubrics(id) ON DELETE SET NULL,
  score_value DOUBLE PRECISION,
  score_max_value DOUBLE PRECISION,
  score_percent DOUBLE PRECISION,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (article_id, lens_id, rubric_id)
);

CREATE TABLE IF NOT EXISTS public.snapshots (
  snapshot_date DATE PRIMARY KEY,
  import_run_id UUID REFERENCES public.import_runs(id) ON DELETE SET NULL,
  source_url TEXT,
  generated_at TIMESTAMPTZ,
  article_count INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.derived_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  import_run_id UUID REFERENCES public.import_runs(id) ON DELETE SET NULL,
  snapshot_key TEXT NOT NULL DEFAULT 'current',
  snapshot_date DATE,
  metric_key TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (snapshot_key, metric_key)
);

CREATE TABLE IF NOT EXISTS public.analysis_runs (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  model TEXT NOT NULL,
  sentiment TEXT NOT NULL,
  score DOUBLE PRECISION,
  input_text TEXT NOT NULL,
  processed_text TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_import_runs_created_at ON public.import_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON public.articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON public.articles (source_id);
CREATE INDEX IF NOT EXISTS idx_article_tags_tag ON public.article_tags (tag_type, tag_normalized);
CREATE INDEX IF NOT EXISTS idx_article_scores_lens_id ON public.article_scores (lens_id);
CREATE INDEX IF NOT EXISTS idx_derived_metrics_metric_key ON public.derived_metrics (metric_key);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at ON public.analysis_runs (created_at DESC);
