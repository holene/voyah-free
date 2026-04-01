# Migrating manual docs to PDF pipeline output

This repo can publish two kinds of Starlight pages:

1. **Hand-authored** — `src/content/docs/overview/`, `technical/`, `triplescreen/` (English, root locale).
2. **Generated from PDFs** — `src/content/docs/from-sources/` (English canonical) and `src/content/docs/no/from-sources/` (Norwegian canonical or translated counterparts).

## Phasing strategy

1. Run `npm run pipeline:all` after adding or changing files in `src/raw/pdfs/`.
2. Compare the generated page in `from-sources` (or `no/from-sources`) with any overlapping manual topic.
3. When satisfied, remove or redirect the manual page:
   - Prefer keeping stable URLs: replace the body of the manual page with a short note and a link to the new canonical URL, or use your host’s redirects.
4. English and Norwegian URLs for the same `doc_id` should stay aligned (`/from-sources/{doc_id}` vs `/no/from-sources/{doc_id}`) so the language switcher can fall back correctly.

## Environment

- **Extraction** is offline (PyMuPDF). No API keys required.
- **Translation / optional LLM polish** uses an OpenAI-compatible API when `OPENAI_API_KEY` or `PIPELINE_LLM_API_KEY` is set.
- Optional: `PIPELINE_LLM_BASE_URL`, `PIPELINE_LLM_MODEL`, `PIPELINE_LLM_CANONICAL=1` (canonical polish).

## Git hygiene

- `src/raw/extracted/` and `src/raw/normalized/` are gitignored; regenerate locally or in CI.
- Commit generated `.mdx` under `from-sources` and assets under `public/from-pdf/` so `npm run build` works without Python.

## CI

See `.github/workflows/docs-pipeline.yml`: installs Python dependencies, runs the pipeline, then `npm ci` and `npm run build`.
