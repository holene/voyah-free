# Voyah Free Docs

Astro + Starlight documentation site for community-maintained `Voyah Free` documentation.

The repo contains two kinds of content:

- Hand-authored docs under `src/content/docs/overview/`, `src/content/docs/technical/`, and `src/content/docs/triplescreen/`
- Generated docs from source PDFs under `src/content/docs/from-sources/` and `src/content/docs/no/from-sources/`

## Project Structure

```text
.
├── docs/
├── public/
├── src/
│   ├── content/docs/
│   │   ├── overview/
│   │   ├── technical/
│   │   ├── triplescreen/
│   │   ├── from-sources/
│   │   └── no/from-sources/
│   └── raw/
│       ├── pdfs/
│       ├── extracted/      # generated, gitignored
│       └── normalized/     # generated, gitignored
├── tools/pipeline/
├── astro.config.mjs
└── package.json
```

## Local Development

Install the site dependencies and run the docs site:

```bash
npm install
npm run dev
```

Useful commands:

| Command | Action |
| :------ | :----- |
| `npm run dev` | Start local dev server on `localhost:4321` |
| `npm run build` | Build the site to `dist/` |
| `npm run preview` | Preview the production build locally |
| `npm run astro -- --help` | Show Astro CLI help |

## PDF Extraction Pipeline

The PDF pipeline is implemented in Python and wrapped by npm scripts. It reads PDFs from `src/raw/pdfs/`, generates intermediate JSON, optionally runs LLM-assisted stages, and renders MDX pages for Starlight.

### One-time setup

Use Python `3.11+` for the pipeline:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r tools/pipeline/requirements.txt
```

### Run the full pipeline

1. Add one or more `.pdf` files to `src/raw/pdfs/`
2. Activate the virtualenv
3. Run:

```bash
npm run pipeline:all
```

That command runs these stages in order:

1. `extract`
2. `chunk`
3. `canonicalize`
4. `translate`
5. `qa`
6. `render`

### Run individual stages

| Command | Action |
| :------ | :----- |
| `npm run pipeline:extract` | Extract text/images from PDFs into `src/raw/extracted/` |
| `npm run pipeline:chunk` | Build chunk JSON from extracted pages |
| `npm run pipeline:canonicalize` | Build `canonical.*.json` into `src/raw/normalized/` |
| `npm run pipeline:translate` | Create `translated.*.json` when LLM env is configured |
| `npm run pipeline:qa` | Write `src/raw/extracted/qa-report.json` |
| `npm run pipeline:render` | Render MDX pages and copy extracted images to `public/from-pdf/` |
| `npm run pipeline:all` | Run the full pipeline end-to-end |

If you need to force re-extraction even when the PDF hash has not changed, run the Python CLI directly:

```bash
PYTHONPATH=tools/pipeline python3 -m voyah_pipeline.cli extract --force
```

### Output behavior

- `src/raw/extracted/` contains extracted page JSON, chunks, images, OCR status, the manifest, and QA report
- `src/raw/normalized/` contains canonical and translated document JSON per `doc_id`
- `src/content/docs/from-sources/` contains English pages
- `src/content/docs/no/from-sources/` contains Norwegian pages
- `public/from-pdf/<doc_id>/` contains extracted images referenced by generated pages

Language handling is based on the document’s detected source language:

- If the source PDF is English, the canonical page is rendered to `src/content/docs/from-sources/`
- If the source PDF is Norwegian, the canonical page is rendered to `src/content/docs/no/from-sources/`
- If LLM translation is enabled, the pipeline also writes a translated counterpart into the opposite locale

### LLM configuration

Extraction, chunking, deterministic canonicalization, QA, and rendering are offline. No API key is required for those stages.

Translation only runs when an OpenAI-compatible API is configured through one of:

- `OPENAI_API_KEY`
- `PIPELINE_LLM_API_KEY`

Optional settings:

- `PIPELINE_LLM_BASE_URL`
- `PIPELINE_LLM_MODEL`
- `PIPELINE_LLM_CANONICAL=1` to enable optional LLM polishing during canonicalization

Without LLM credentials, `translate` produces no translated output, which is valid current behavior.

### QA and generated content

- QA output is written to `src/raw/extracted/qa-report.json`
- The pipeline reports schema and content flags, but `pipeline:all` does not fail on non-schema QA findings
- `src/raw/extracted/` and `src/raw/normalized/` are intentionally gitignored
- Generated `.mdx` content under `from-sources/` should be committed so the site can build without rerunning Python locally

See `docs/MIGRATION.md` for guidance on replacing overlapping manual pages with generated ones.

## CI

CI installs Python pipeline dependencies, runs the full pipeline, then installs Node dependencies and builds the Astro site. See `.github/workflows/docs-pipeline.yml`.
