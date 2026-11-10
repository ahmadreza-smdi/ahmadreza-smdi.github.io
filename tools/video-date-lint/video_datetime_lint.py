#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ahmadreza Samadi
"""Offline publication-date checks for HTML JSON-LD and video sitemaps."""

import argparse
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
VIDEO_NS = "http://www.google.com/schemas/sitemap-video/1.1"
IGNORED_DIRS = {".git", "node_modules", "__pycache__"}
VIDEO_TYPES = {"VideoObject", "https://schema.org/VideoObject", "http://schema.org/VideoObject"}


class JsonLdScripts(HTMLParser):
    """Collect script bodies without depending on attribute layout or quote style."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        mime = next((v for k, v in attrs if k.lower() == "type"), None)
        if isinstance(mime, str) and mime.strip().lower() == "application/ld+json":
            self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            self.blocks.append("".join(self.current))
            self.current = None

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def json_pointer_part(key):
    return key.replace("~", "~0").replace("/", "~1")


def find_videos(value, pointer=""):
    if isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if isinstance(types, list) and any(isinstance(t, str) and t in VIDEO_TYPES for t in types):
            yield pointer, value
        for key, child in value.items():
            yield from find_videos(child, pointer + "/" + json_pointer_part(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from find_videos(child, pointer + "/" + str(index))


def unique_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key: " + key)
        result[key] = value
    return result


def reject_nonstandard_json_constant(value):
    raise ValueError("nonstandard JSON constant: " + value)


def parse_timestamp(value):
    """Return (precision, aware instant or None), or raise a descriptive ValueError.

    The supported profile is YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[.ffffff][Z|+HH:MM|-HH:MM].
    An absent offset and a date alone deliberately produce no invented instant.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("must be a nonempty string")
    day, separator, clock = value.partition("T")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
        raise ValueError("unsupported date format; expected YYYY-MM-DD")
    try:
        calendar = datetime.strptime(day, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("impossible calendar date") from exc
    if not separator:
        return "date", None
    match = re.fullmatch(r"([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{1,6}))?(Z|[+-][0-9]{2}:[0-9]{2})?", clock)
    if match is None:
        raise ValueError("unsupported time format; expected HH:MM:SS with optional fraction and offset")
    hour, minute, second = (int(match.group(i)) for i in (1, 2, 3))
    micros = int((match.group(4) or "0").ljust(6, "0"))
    try:
        local = calendar.replace(hour=hour, minute=minute, second=second, microsecond=micros)
    except ValueError as exc:
        raise ValueError("impossible clock time") from exc
    offset = match.group(5)
    if offset is None:
        return "local_datetime", None
    if offset == "Z":
        zone = timezone.utc
    else:
        hours, minutes = int(offset[1:3]), int(offset[4:6])
        if hours > 23 or minutes > 59:
            raise ValueError("offset hours must be 00..23 and minutes 00..59")
        sign = 1 if offset.startswith("+") else -1
        zone = timezone(sign * timedelta(hours=hours, minutes=minutes))
    return "aware_datetime", local.replace(tzinfo=zone)


class Audit:
    def __init__(self, now, strict_datetime, require_sitemap_dates, require_video):
        self.now = now
        self.strict = strict_datetime
        self.require_sitemap_dates = require_sitemap_dates
        self.require_video = require_video
        self.diagnostics = []
        self.occurrences = []
        self.by_content_url = {}
        self.parse_failed = False
        self.counts = dict(html_files=0, jsonld_blocks=0, video_objects=0,
                           sitemap_files=0, sitemap_videos=0,
                           repeated_video_comparisons=0, sitemap_comparisons=0,
                           skipped_consistency_checks=0)

    def add(self, path, location, code, severity, message, value=None):
        self.diagnostics.append(dict(path=str(path), location=location, code=code,
                                     severity=severity, message=message, value=value))

    def input_error(self, path, location, code, message):
        self.parse_failed = True
        self.add(path, location, code, "error", message)

    def check_date(self, path, location, value, sitemap=False):
        if sitemap and value is None and not self.require_sitemap_dates:
            return None
        if value is None:
            self.add(path, location, "missing_publication_date", "error", "publication date is required by the selected policy")
            return None
        try:
            precision, instant = parse_timestamp(value)
        except ValueError as exc:
            self.add(path, location, "invalid_publication_date", "error", str(exc), value)
            return None
        severity = "error" if self.strict else "warning"
        if precision == "date" and (not sitemap or self.strict):
            self.add(path, location, "date_without_time", severity,
                     "date alone cannot establish a publication instant; strict policy requires full datetime and timezone", value)
        elif precision == "local_datetime":
            self.add(path, location, "missing_timezone", severity,
                     "timezone absent; no timezone or publication instant was guessed", value)
        if instant is not None and instant > self.now:
            self.add(path, location, "future_publication_date", "error",
                     "publication instant is after the selected clock (local pre-publication policy)", value)
        return instant

    def read_html(self, path):
        self.counts["html_files"] += 1
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            self.input_error(path, "", "unreadable_html", str(exc))
            return
        parser = JsonLdScripts()
        try:
            parser.feed(text)
            parser.close()
        except Exception as exc:
            self.input_error(path, "", "html_parse_error", str(exc))
            return
        if parser.current is not None:
            self.input_error(path, "", "unclosed_jsonld_script", "JSON-LD script has no closing script tag")
        for number, body in enumerate(parser.blocks, 1):
            self.counts["jsonld_blocks"] += 1
            location = "script[" + str(number) + "]"
            try:
                payload = json.loads(body, object_pairs_hook=unique_json_keys,
                                     parse_constant=reject_nonstandard_json_constant)
            except (ValueError, RecursionError) as exc:
                self.input_error(path, location, "invalid_jsonld", str(exc))
                continue
            if payload is None or (isinstance(payload, (dict, list)) and not payload):
                self.add(path, location, "empty_jsonld_document", "info",
                         "empty object, array or null document; no VideoObjects to inspect")
                continue
            if not isinstance(payload, (dict, list)):
                self.input_error(path, location, "unsupported_jsonld_document",
                                 "JSON-LD document root must be an object, array or null; scalar roots are unsupported")
                continue
            try:
                for pointer, node in find_videos(payload):
                    self.counts["video_objects"] += 1
                    where = location + pointer
                    instant = self.check_date(path, where + "/uploadDate", node.get("uploadDate"))
                    identity = node.get("contentUrl")
                    if not isinstance(identity, str) or not identity.strip():
                        identity = None
                        self.add(path, where + "/contentUrl", "missing_video_identity", "info",
                                 "no contentUrl string; exact cross-file identity check unavailable")
                    occurrence = dict(path=str(path), location=where, content_url=identity,
                                      instant=instant, upload_date=node.get("uploadDate"))
                    self.occurrences.append(occurrence)
                    if identity is not None:
                        self.by_content_url.setdefault(identity, []).append(occurrence)
            except RecursionError:
                self.input_error(path, location, "jsonld_nesting_too_deep", "JSON-LD nesting exceeds parser capacity")

    def compare_repeated_videos(self):
        for identity, copies in sorted(self.by_content_url.items()):
            known = [item for item in copies if item["instant"] is not None]
            if len(copies) > 1:
                self.counts["skipped_consistency_checks"] += len(copies) - len(known)
            if not known:
                continue
            first = known[0]
            for other in known[1:]:
                self.counts["repeated_video_comparisons"] += 1
                if other["instant"] != first["instant"]:
                    self.add(other["path"], other["location"] + "/uploadDate", "repeated_video_mismatch", "error",
                             "same exact contentUrl differs from " + first["path"] + " " + first["location"], other["upload_date"])

    def read_sitemap(self, path):
        self.counts["sitemap_files"] += 1
        try:
            root = ET.fromstring(path.read_bytes())
        except (OSError, ET.ParseError, ValueError, LookupError) as exc:
            self.input_error(path, "", "invalid_sitemap", str(exc))
            return
        if root.tag != "{" + SITEMAP_NS + "}urlset":
            self.input_error(path, "", "unsupported_sitemap", "expected a sitemap-namespace urlset; sitemap indexes are unsupported")
            return
        for ui, entry in enumerate(root.findall("{" + SITEMAP_NS + "}url"), 1):
            for vi, video in enumerate(entry.findall("{" + VIDEO_NS + "}video"), 1):
                self.counts["sitemap_videos"] += 1
                where = "url[" + str(ui) + "]/video[" + str(vi) + "]"
                raw = video.findtext("{" + VIDEO_NS + "}publication_date")
                value = raw.strip() if raw is not None else None
                instant = self.check_date(path, where + "/publication_date", value, sitemap=True)
                raw_identity = video.findtext("{" + VIDEO_NS + "}content_loc")
                identity = raw_identity.strip() if raw_identity is not None else None
                if not identity:
                    self.counts["skipped_consistency_checks"] += 1
                    self.add(path, where, "missing_sitemap_identity", "info",
                             "no content_loc; player_loc and inferred identities are outside this tool's matching scope")
                    continue
                matches = self.by_content_url.get(identity, [])
                if not matches:
                    self.counts["skipped_consistency_checks"] += 1
                    self.add(path, where, "unmatched_sitemap_video", "warning",
                             "no VideoObject with this exact contentUrl in supplied HTML; input set may be partial", identity)
                    continue
                known = [item for item in matches if item["instant"] is not None]
                if instant is None or not known:
                    self.counts["skipped_consistency_checks"] += 1
                    continue
                self.counts["sitemap_comparisons"] += 1
                if any(item["instant"] != instant for item in known):
                    first = next(item for item in known if item["instant"] != instant)
                    self.add(path, where + "/publication_date", "sitemap_video_mismatch", "error",
                             "publication instant differs from " + first["path"] + " " + first["location"], value)

    def report(self):
        if self.require_video and not self.counts["video_objects"]:
            self.add("", "", "no_video_objects", "error", "--require-video needs at least one discovered VideoObject")
        diagnostics = sorted(self.diagnostics, key=lambda d: (d["path"], d["location"], d["code"], d["severity"]))
        counts = dict(self.counts)
        counts.update({plural: sum(d["severity"] == singular for d in diagnostics)
                       for singular, plural in [("error", "errors"), ("warning", "warnings"), ("info", "infos")]})
        exit_code = 2 if self.parse_failed else 1 if counts["errors"] else 0
        return dict(schema_version=1, tool="video_datetime_lint", now_utc=self.now.astimezone(timezone.utc).isoformat(),
                    policy=dict(strict_datetime=self.strict, require_sitemap_dates=self.require_sitemap_dates,
                                require_video=self.require_video, future_instants="error", identity="exact contentUrl/content_loc"),
                    counts=counts, diagnostics=diagnostics, exit_code=exit_code)


def write_output_line(message):
    """Keep diagnostics printable on restrictive streams without dropping characters."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe = message.encode(encoding, errors="backslashreplace").decode(encoding)
    sys.stdout.write(safe + "\n")


def main(argv=None):
    args_parser = argparse.ArgumentParser(description=__doc__)
    args_parser.add_argument("paths", nargs="*", help="HTML files or directories (recursive *.html/*.htm)")
    args_parser.add_argument("--sitemap", action="append", default=[], help="optional local video sitemap XML; repeatable")
    args_parser.add_argument("--now", help="inject an aware full datetime clock, e.g. 2026-10-10T00:00:00Z")
    args_parser.add_argument("--strict-datetime", action="store_true", help="make date-only/timezone-free publication values errors")
    args_parser.add_argument("--require-sitemap-dates", action="store_true", help="require optional sitemap publication_date tags (project policy)")
    args_parser.add_argument("--require-video", action="store_true", help="fail an HTML scan with no discovered VideoObjects")
    args_parser.add_argument("--format", choices=["text", "json"], default="text")
    args = args_parser.parse_args(argv)
    if not args.paths and not args.sitemap:
        args_parser.error("provide at least one HTML path or --sitemap")
    now = datetime.now(timezone.utc)
    if args.now:
        try:
            precision, parsed = parse_timestamp(args.now)
            if precision != "aware_datetime":
                raise ValueError("requires full datetime with explicit timezone")
            now = parsed.astimezone(timezone.utc)
        except OverflowError:
            args_parser.error("--now cannot be represented within Python's UTC datetime range")
        except ValueError as exc:
            args_parser.error("--now " + str(exc))
    audit = Audit(now, args.strict_datetime, args.require_sitemap_dates, args.require_video)
    html_paths = set()
    for name in args.paths:
        path = Path(name).absolute()
        if path.is_dir():
            try:
                for file in path.rglob("*"):
                    if file.is_file() and file.suffix.lower() in {".html", ".htm"} and not any(p in IGNORED_DIRS for p in file.relative_to(path).parts):
                        html_paths.add(file)
            except OSError as exc:
                audit.input_error(path, "", "unreadable_directory", str(exc))
        elif path.is_file():
            html_paths.add(path)
        else:
            audit.input_error(path, "", "missing_input", "HTML path does not exist or is not a regular file/directory")
    for path in sorted(html_paths):
        audit.read_html(path)
    audit.compare_repeated_videos()
    for path in sorted({Path(name).absolute() for name in args.sitemap}):
        audit.read_sitemap(path)
    report = audit.report()
    if args.format == "json":
        write_output_line(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        counts = report["counts"]
        write_output_line("Scanned {html_files} HTML files, {jsonld_blocks} JSON-LD blocks, {video_objects} VideoObjects, "
              "{sitemap_files} sitemaps, {sitemap_videos} sitemap videos.".format(**counts))
        for diagnostic in report["diagnostics"]:
            write_output_line("{severity} {code}: {path} {location}: {message}".format(**diagnostic))
        write_output_line("{errors} errors, {warnings} warnings, {infos} info; exit {exit_code}.".format(exit_code=report["exit_code"], **counts))
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
