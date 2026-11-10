"""Build a reviewed GitHub Pages tree locally. No network access or deployment."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile

from check_internal_links import VERIFICATION, protected
from check_site_live import committed_csv, excluded_files
from site_resources import inventory

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = {
    ".nojekyll", "CNAME", "404.html", "robots.txt", "sitemap.xml", "humans.txt",
    "site.webmanifest", "ask-index.json", "llms.txt", "llms-full.txt", "writing/feed.xml",
}
MANIFEST = "publish-extra.json"


def internal(path):
    return path.startswith(("scripts/", "locales/")) or bool(
        re.match(r"data/[^/]+-publications/", path)
    ) or path == "data/seo-baseline.json"


def allowed(path):
    parts = PurePosixPath(path).parts
    if not parts or path != "/".join(parts) or "\\" in path or any(
        part == ".." or part.startswith(".git") or "vault" in part.casefold()
        or part.casefold() in {"cv", "important-docs"} for part in parts
    ):
        return False
    return not protected(path) or bool(len(parts) == 1 and VERIFICATION.fullmatch(path))


def tracked_files(root):
    result = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=root)
    tracked = {}
    for entry in result.split(b"\0"):
        if entry:
            meta, raw_path = entry.split(b"\t", 1)
            mode, _, stage = meta.split()
            if stage != b"0":
                raise ValueError("Resolve the Git index conflicts before publishing")
            tracked[os.fsdecode(raw_path)] = mode.decode()
    return tracked


def select(root, withdraw_internal=False):
    tracked = tracked_files(root)
    html, reached, references, missing = inventory(root)
    if not html or missing:
        examples = "; ".join(f"{p} -> {q}" for p, q in sorted(missing)[:8])
        raise ValueError(f"Cannot publish: {len(missing)} missing references. {examples}")
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    extra = manifest["extra"]
    if not isinstance(extra, dict) or any(not isinstance(r, str) or not r.strip() for r in extra.values()):
        raise ValueError("Every additional path requires a reviewed reason")
    discovery = DISCOVERY | {p for p in tracked if "/" not in p and VERIFICATION.fullmatch(p)}
    selected = reached | discovery | extra.keys()
    excluded = set(excluded_files(root))
    if excluded & selected or MANIFEST in selected:
        raise ValueError("Public inputs include a repository-only file")
    if withdraw_internal:
        removed = {p for p in selected if internal(p)}
        for dest in removed:
            if references.get(dest, set()) - removed:
                raise ValueError(f"A public document still references the withdrawn path {dest}")
        selected -= removed
    for p in sorted(selected):
        if not allowed(p) or tracked.get(p) not in {"100644", "100755"}:
            raise ValueError(f"Unsafe, untracked or non-regular public path: {p}")
        file = root / p
        if not file.is_file() or file.resolve() != file:
            raise ValueError(f"Missing file or symbolic link: {p}")
    return sorted(selected)


def build(root, output, withdraw_internal=False):
    root, output = root.resolve(), output.absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(root):
        raise ValueError("Use a new destination outside the repository")
    selected = select(root, withdraw_internal)
    # Rename a completed tree into place; a failed build leaves the destination absent.
    with tempfile.TemporaryDirectory(dir=output.parent) as scratch:
        staging = Path(scratch) / "tree"
        staging.mkdir()
        for path in selected:
            src, dest = root / path, staging / path
            dest.parent.mkdir(exist_ok=True, parents=True)
            if src.suffix == ".csv":
                data, _ = committed_csv(root, path)
                dest.write_bytes(data)
            else:
                shutil.copyfile(src, dest)
        if output.exists() or output.is_symlink():
            raise ValueError("Destination appeared during build")
        staging.rename(output)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--output", type=Path)
    parser.add_argument("--withdraw-internal", action="store_true", help="Owner decision; default is to preserve existing public URLs.")
    args = parser.parse_args()
    try:
        files = select(ROOT, args.withdraw_internal) if args.check else build(ROOT, args.output, args.withdraw_internal)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"FAIL: {error}\n")
    print(f"PASS: {len(files)} public files; withdraw internal = {args.withdraw_internal}")


if __name__ == "__main__":
    main()

