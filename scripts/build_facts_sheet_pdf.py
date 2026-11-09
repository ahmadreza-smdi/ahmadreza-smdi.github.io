"""Build the English facts sheet with the original portrait, layout and live links.

The only design source in the repository is the October PDF. Supply that exact
template as the first argument and a separate destination as the second.
Requires pypdf. No network access.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import argparse

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ByteStringObject, NumberObject

TEMPLATE_SHA256 = "ed936749f74ea12790d27fc49dc6bebd1f33f0869af2c55f4a5fb8291fedf58c"
SUMMARY = "I build AI, and I run a business that has to live with it."


def build(template):
    if sha256(template).hexdigest() != TEMPLATE_SHA256:
        raise ValueError("Expected the original one-page October 2026 template")
    writer = PdfWriter(clone_from=PdfReader(BytesIO(template)))
    page = writer.pages[0]
    content = page.get_contents()
    matches = [i for i, (args, op) in enumerate(content.operations)
               if op == b"Tj" and str(args[0]) == "Also known as Ahmad Samadi"]
    if len(matches) != 1:
        raise ValueError("The template must have exactly one alias line")
    # Place the brand line under the alias, inside the name panel.
    i = matches[0] + 1
    content.operations[i:i] = [
        ([NumberObject(0), NumberObject(-15)], b"Td"),
        ([ByteStringObject(SUMMARY.encode("ascii"))], b"Tj"),
    ]
    page.replace_contents(content)
    writer.add_metadata({"/Subject": SUMMARY, "/ModDate": "D:20261109"})
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.template.resolve() == args.output.resolve():
        parser.error("Use a separate destination to preserve the template")
    result = build(args.template.read_bytes())
    if not args.output.exists() or args.output.read_bytes() != result:
        args.output.write_bytes(result)
