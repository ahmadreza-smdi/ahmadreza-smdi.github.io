"""Inspect public text resources, vCards, PDFs and archived documents without executing their contents."""

from io import BytesIO
from pathlib import Path
import subprocess
import zipfile
from check_internal_links import protected

TEXT = {
    ".txt",
    ".md",
    ".csv",
    ".tsv",
    ".json",
    ".vcf",
    ".html",
    ".xml",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".css",
    ".toml",
    ".rst",
}


def pdf_text(data):
    try:
        from pypdf import PdfReader
    except ImportError:
        yield subprocess.check_output(["pdftotext", "-", "-"], input=data).decode(
            "utf-8"
        )
        yield subprocess.check_output(["pdfinfo", "-url", "-"], input=data).decode(
            "utf-8"
        )
        return
    reader = PdfReader(BytesIO(data))
    for page in reader.pages:
        yield page.extract_text() or ""
        for ref in page.get("/Annots", []):
            obj = ref.get_object()
            action = obj.get("/A", {})
            if action and action.get("/URI"):
                yield str(action["/URI"])


def documents(path, data, depth=0):
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        yield path, "\n".join(pdf_text(data))
    elif ext in (".zip", ".xlsx"):
        with zipfile.ZipFile(BytesIO(data)) as bundle:
            for entry in bundle.infolist():
                if entry.is_dir():
                    continue
                name = Path(entry.filename)
                if protected(name) or ".." in name.parts or name.is_absolute():
                    raise ValueError("archive member requires private review")
                if name.suffix.lower() not in TEXT | {".pdf", ".zip", ".xlsx"}:
                    continue
                if depth >= 4 or entry.file_size > 64_000_000:
                    raise ValueError("archive exceeds review limits")
                yield from documents(
                    path + "!" + entry.filename, bundle.read(entry), depth + 1
                )
    elif ext in TEXT:
        yield path, data.decode("utf-8-sig", errors="replace")


def downloads(root):
    folders = ["assets", "studies", "tools"]
    paths = set(root.glob("llms*.txt"))
    for directory in folders:
        for p in (root / directory).rglob("*"):
            if p.is_symlink() or not p.is_file() or protected(p.relative_to(root)):
                continue
            if p.suffix.lower() in (".zip", ".xlsx", ".vcf", ".pdf") or (
                p.suffix.lower() == ".txt"
                and (
                    "profile" in p.parts
                    or "downloads" in p.parts
                    or "resources" in p.parts
                )
            ):
                paths.add(p)
    for p in sorted(paths):
        yield p.relative_to(root).as_posix(), p
