from __future__ import annotations

import argparse
import sys

from voyah_pipeline.canonicalize import canonicalize_all
from voyah_pipeline.extract import extract_all
from voyah_pipeline.chunking import chunk_all_from_manifest
from voyah_pipeline.qa import qa_fail_on_errors, qa_report_all
from voyah_pipeline.render_mdx import render_all_from_manifest, write_generated_index_stub
from voyah_pipeline.translate import translate_all_from_manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Voyah Free PDF docs pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ex = sub.add_parser("extract", help="Extract PDFs to src/raw/extracted")
    p_ex.add_argument("--force", action="store_true", help="Re-extract even if SHA-256 unchanged")
    sub.add_parser("chunk", help="Build chunk JSON from extracted pages")
    sub.add_parser("canonicalize", help="Build canonical.*.json under src/raw/normalized")
    sub.add_parser("translate", help="Translate canonical JSON when LLM env is set")
    sub.add_parser("qa", help="Run QA checks and write qa-report.json")
    sub.add_parser("render", help="Render MDX + copy images to public/")
    sub.add_parser("all", help="extract → chunk → canonicalize → translate → qa → render")

    args = p.parse_args(argv)

    if args.cmd == "extract":
        extract_all(force=args.force)
        return 0
    if args.cmd == "chunk":
        chunk_all_from_manifest()
        return 0
    if args.cmd == "canonicalize":
        extract_all(force=False)
        chunk_all_from_manifest()
        canonicalize_all()
        return 0
    if args.cmd == "translate":
        translate_all_from_manifest()
        return 0
    if args.cmd == "qa":
        qa_report_all()
        return qa_fail_on_errors(strict=False)
    if args.cmd == "render":
        write_generated_index_stub()
        render_all_from_manifest()
        return 0
    if args.cmd == "all":
        extract_all(force=False)
        chunk_all_from_manifest()
        canonicalize_all()
        translate_all_from_manifest()
        qa_report_all()
        code = qa_fail_on_errors(strict=False)
        write_generated_index_stub()
        render_all_from_manifest()
        return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
