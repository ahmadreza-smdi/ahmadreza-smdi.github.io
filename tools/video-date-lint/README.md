# Offline video publication-date linter

This original standard-library Python CLI checks publication dates in local HTML JSON-LD and optional video sitemap XML. It catches impossible dates, absent timezones, future publication instants, and inconsistent instants for repeated exact video URLs. It reads inputs without changing them and makes no network requests.

Developed with AI assistance for this repository and reviewed with synthetic behavioral fixtures. This utility is original code; it does not import website implementation or third-party packages.

## Run

Use Python 3.10 or newer. No dependency installation is needed. Run the following commands from this utility directory (or use its full script path from another directory). On Windows, use `python` if `python3` is unavailable.

```sh
python3 video_datetime_lint.py path/to/site --sitemap path/to/site/sitemap.xml
python3 video_datetime_lint.py page.html --format json --now 2026-10-10T00:00:00Z
python3 video_datetime_lint.py path/to/site --sitemap sitemap.xml --strict-datetime --require-sitemap-dates --require-video
python3 -B -m unittest discover -s tests -v
```

The directory scan includes `.html` and `.htm` recursively and excludes `.git`, `node_modules` and `__pycache__`. Explicit file arguments are read as HTML. Inputs are deduplicated by absolute path. A sitemap index is unsupported; pass its individual video sitemap files with repeated `--sitemap` arguments.

## Policies and outcomes

The supported date profile is `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS[.ffffff][Z|±HH:MM]`, with ASCII digits and one to six fractional digits. Calendar dates, clock fields and numeric offset components are checked. Leap seconds, alternate ISO spellings, remote JSON-LD contexts, microdata and RDFa are outside this tool. Missing offsets never inherit the machine timezone or a guessed historical time.

Default behavior:

- Missing or nonstring `VideoObject.uploadDate`, impossible/unsupported timestamps and future aware instants are errors. The future rule is a local publication policy, not a claim about every Google use case.
- A date-only upload date or timezone-free datetime is a warning. It cannot be compared as an instant. Numeric offsets and `Z` are compared by the represented instant, so different calendar days can still agree.
- Video sitemap `publication_date` is optional, and a valid date-only value is accepted. An absent/date-only value cannot establish an exact instant for comparison.
- `--strict-datetime` makes date-only or timezone-free publication values errors; it does not require an absent optional sitemap date. `--require-sitemap-dates` adds that separate project requirement.
- Matching uses exact `VideoObject.contentUrl` and sitemap `video:content_loc` strings. It does not infer identities from titles, normalize relative URLs, or use `embedUrl`, `@id` or `player_loc` as substitutes. Missing identity and incomplete comparisons are reported through diagnostics/counts. An unmatched sitemap video is a warning because the HTML input set may be partial.
- A zero-video scan reports zero rather than implying meaningful video validation. `--require-video` makes that an error.

HTML script parsing accepts attribute order, extra attributes, casing and quote variants. JSON-LD objects, arrays, graphs, nested nodes and list-valued types are inspected. Compact `VideoObject` and the HTTP/HTTPS schema.org type URLs are supported. Empty objects, arrays and null documents produce an explicit informational diagnostic; a scalar root is an unsupported input failure. Malformed JSON, duplicate keys, nonstandard constants and malformed XML are input failures; they are never silently ignored.

Exit codes are `0` for no errors (warnings may remain), `1` for lint/policy errors, and `2` for input/parse/usage failure. JSON reports have sorted keys and stable diagnostic order with a fixed `--now` clock; text reports include scan counts and diagnostic codes. JSON output uses ASCII escapes so decoded strings, including invalid-date lone surrogates, remain representable in the report. Text output backslash-escapes characters that the active output encoding cannot represent, including diagnostic paths and duplicate-key messages. Unknown XML declared encodings produce input-failure diagnostics. Argument-parser usage errors go to stderr rather than emitting a JSON scan report. Injected clocks must be representable in UTC within Python's datetime range; overflowing boundary offsets are rejected as usage errors. No output-file option or automatic repair is provided.

## What this does not prove

Syntax and internal consistency cannot prove a timestamp is the real first publication, that a video will be indexed, or that rich results or rankings will improve. A page can pass this narrow tool while failing other structured-data, video, accessibility or indexing requirements. Partially supplied files limit consistency checks. Symlink aliases are not resolved into one identity; the same file supplied through different aliases may be counted twice. Only the supported timestamp subset is assessed.

Google currently recommends timezone information for `uploadDate`; this tool's strict timezone rule is an explicit policy. Google lists video sitemap `publication_date` as optional and accepts date alone. Current source checks: [Video structured data](https://developers.google.com/search/docs/appearance/structured-data/video), [video sitemap tags](https://developers.google.com/search/docs/crawling-indexing/sitemaps/video-sitemaps), reviewed 10 October 2026.

The test fixtures are synthetic and include real warning-value shapes from the completed publication-date repair. They exercise the CLI independently, check exit contracts and represented instants, and hash inputs before/after. They do not use website source as test expected output. The behavioral suite runs in GitHub Actions on Linux and Windows with Python 3.10 and 3.13. Passing these fixtures does not establish indexing or ranking outcomes.

## License

[MIT](LICENSE), Copyright (c) 2026 Ahmadreza Samadi. The license applies only to files within `tools/video-date-lint/`. It does not relicense the surrounding website, photographs, films, fonts or other repository resources.
