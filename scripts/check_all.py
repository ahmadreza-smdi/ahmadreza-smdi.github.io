"""Run the repository's local checks by hand. Only --live permits public site requests."""

import argparse
import csv
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".py", ".mjs", ".cjs"}


def commands(root, live, gallery_receipt=None, article_receipt=None, live_report=None):
    scripts = root / "scripts"
    conventional = root / "Gallery-Prepared.json"
    if gallery_receipt is None and (conventional.exists() or conventional.is_symlink()):
        gallery_receipt = conventional
    candidates = set(scripts.rglob("test_*")) | set((root / "tools").rglob("test_*"))
    candidates |= set(scripts.glob("check_*")) | set(scripts.glob("build_*.py"))
    additional = {"enrich_metadata.py", "enrich_study_metadata.py", "follow_blocks.py"}
    candidates.update(scripts / name for name in additional)
    for path in sorted(candidates):
        if (
            not path.is_file()
            or path.suffix not in SUFFIXES
            or path.name == "check_all.py"
            or "fixtures" in path.parts
        ):
            continue
        rel = path.relative_to(root).as_posix()
        args = [sys.executable if path.suffix == ".py" else "node", rel]
        reason = ""
        if path.name.startswith("build_") or path.name in additional:
            if "--check" not in path.read_text():
                raise ValueError(
                    f"{rel} needs an explicit read-only mode before it can join the runner"
                )
            args.append("--check")
        if path.name == "check_site_live.py":
            if live:
                args.append("--live")
                if live_report:
                    args.extend(["--json", str(live_report)])
            else:
                reason = "network check requires --live"
        if path.name == "check_new_carousel_titles.py" and gallery_receipt:
            args.extend(["--receipt", str(gallery_receipt)])
        if path.name == "check_new_article_titles.py" and article_receipt:
            args.extend(["--release-receipt", str(article_receipt)])
        elif path.name == "check_new_article_titles.py" and gallery_receipt:
            reason = "gallery batch: the strict gallery check validates every new and changed HTML file"
        yield rel, args, reason


def run(
    root,
    live=False,
    output=None,
    gallery_receipt=None,
    article_receipt=None,
    live_report=None,
):
    rows = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_TERMINAL_PROMPT="0")
    for rel, args, reason in commands(
        root, live, gallery_receipt, article_receipt, live_report
    ):
        started = time.monotonic()
        if reason:
            status = "SKIP"
        else:
            try:
                p = subprocess.run(
                    args,
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    errors="replace",
                )
                lines = (p.stdout + "\n" + p.stderr).strip().splitlines()
                status = "FAIL" if p.returncode else "PASS"
                if not p.returncode and any(line.startswith("SKIP:") for line in lines):
                    status = "SKIP"
                if status == "FAIL":
                    reason = next(
                        (line for line in reversed(lines) if line.strip()),
                        "nonzero exit",
                    )
                elif status == "SKIP":
                    reason = next(
                        line.removeprefix("SKIP:").strip()
                        for line in lines
                        if line.startswith("SKIP:")
                    )
                else:
                    reason = next(
                        (line for line in reversed(lines) if line.strip()), "completed"
                    )
                diagnostics = [
                    line
                    for line in lines
                    if line.startswith(("WARN SEO-", "FAIL BR-", "FAIL SEO-"))
                ]
                if diagnostics:
                    reason = " | ".join([reason, *diagnostics])
            except OSError as error:
                status, reason = "FAIL", str(error)
        seconds = round(time.monotonic() - started, 3)
        print(f"{status}  {rel} ({seconds:.2f}s)  {reason}", flush=True)
        rows.append(dict(check=rel, status=status, seconds=seconds, reason=reason))
    if output:
        with output.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return int(any(row["status"] == "FAIL" for row in rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--csv", type=Path)
    parser.add_argument(
        "--live-report",
        type=Path,
        help="Save URL-level results for the optional live check",
    )
    parser.add_argument("--gallery-receipt", type=Path)
    parser.add_argument("--article-receipt", type=Path)
    args = parser.parse_args()
    if args.live_report and not args.live:
        parser.error("--live-report requires --live")
    sys.exit(
        run(
            ROOT,
            args.live,
            args.csv,
            args.gallery_receipt,
            args.article_receipt,
            args.live_report,
        )
    )
