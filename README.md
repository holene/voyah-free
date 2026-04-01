# Starlight Starter Kit: Basics

[![Built with Starlight](https://astro.badg.es/v2/built-with-starlight/tiny.svg)](https://starlight.astro.build)

```
npm create astro@latest -- --template starlight
```

> 🧑‍🚀 **Seasoned astronaut?** Delete this file. Have fun!

## 🚀 Project Structure

Inside of your Astro + Starlight project, you'll see the following folders and files:

```
.
├── public/
├── src/
│   ├── assets/
│   ├── content/
│   │   └── docs/
│   └── content.config.ts
├── astro.config.mjs
├── package.json
└── tsconfig.json
```

Starlight looks for `.md` or `.mdx` files in the `src/content/docs/` directory. Each file is exposed as a route based on its file name.

Images can be added to `src/assets/` and embedded in Markdown with a relative link.

Static assets, like favicons, can be placed in the `public/` directory.

## PDF → docs pipeline

Source PDFs live in [`src/raw/pdfs/`](src/raw/pdfs/). A Python pipeline extracts text and images, builds canonical JSON, optionally translates via an OpenAI-compatible API, runs QA, and writes Starlight pages under `src/content/docs/from-sources/` (English) and `src/content/docs/no/from-sources/` (Norwegian when that is the PDF source language).

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r tools/pipeline/requirements.txt
npm run pipeline:all
```

Optional env: `OPENAI_API_KEY` or `PIPELINE_LLM_API_KEY`, `PIPELINE_LLM_BASE_URL`, `PIPELINE_LLM_MODEL`, `PIPELINE_LLM_CANONICAL=1`.

Intermediate outputs are gitignored (`src/raw/extracted/`, `src/raw/normalized/`). See [`docs/MIGRATION.md`](docs/MIGRATION.md) for replacing hand-written pages with generated ones.

## 🧞 Commands

All commands are run from the root of the project, from a terminal:

| Command                   | Action                                           |
| :------------------------ | :----------------------------------------------- |
| `npm install`             | Installs dependencies                            |
| `npm run dev`             | Starts local dev server at `localhost:4321`      |
| `npm run build`           | Build your production site to `./dist/`          |
| `npm run preview`         | Preview your build locally, before deploying     |
| `npm run pipeline:all`    | Extract PDFs, normalize, translate (if key set), render MDX |
| `npm run astro ...`       | Run CLI commands like `astro add`, `astro check` |
| `npm run astro -- --help` | Get help using the Astro CLI                     |

## 👀 Want to learn more?

Check out [Starlight’s docs](https://starlight.astro.build/), read [the Astro documentation](https://docs.astro.build), or jump into the [Astro Discord server](https://astro.build/chat).
