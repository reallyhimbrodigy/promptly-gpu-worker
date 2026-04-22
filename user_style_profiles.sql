-- Per-user style profile table.
-- Apply via Supabase SQL editor. Safe to re-run (IF NOT EXISTS).
--
-- Schema rationale: one row per user holds rolling frequency counters for each
-- of their edit choices. After every successful render, handler.update_user_style_profile
-- decays existing counts by 0.92 and adds 1.0 for the fresh pick — recent
-- videos dominate the distribution. On the next Gemini call, the profile is
-- rendered into the prompt so Gemini leans toward the user's accepted style.

CREATE TABLE IF NOT EXISTS public.user_style_profiles (
    user_id               text        PRIMARY KEY,
    caption_styles        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    transitions           jsonb       NOT NULL DEFAULT '{}'::jsonb,
    pacings               jsonb       NOT NULL DEFAULT '{}'::jsonb,
    color_effects         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    text_overlay_variants jsonb       NOT NULL DEFAULT '{}'::jsonb,
    motion_graphics       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    zoom_types            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    recent_vibes          jsonb       NOT NULL DEFAULT '[]'::jsonb,
    avg_emphasis_per_30s  real        NOT NULL DEFAULT 0,
    avg_mgs_per_video     real        NOT NULL DEFAULT 0,
    total_videos          integer     NOT NULL DEFAULT 0,
    updated_at            timestamptz NOT NULL DEFAULT now()
);

-- RLS: the worker uses the service-role key so RLS doesn't gate it, but
-- enable RLS with a deny-all default so no anonymous/authenticated client
-- can read or write these rows from the browser.
ALTER TABLE public.user_style_profiles ENABLE ROW LEVEL SECURITY;

-- Index on updated_at so we can scan for stale profiles if we ever want to
-- expire them.
CREATE INDEX IF NOT EXISTS user_style_profiles_updated_at_idx
    ON public.user_style_profiles (updated_at);
