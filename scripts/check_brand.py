"""Check the personal site's published brand and search rules. Read-only, offline."""

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import csv
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from enrich_metadata import visible_trail
from seo_document import Document, SITE, nodes, public_url
from check_internal_links import site_pages as pages

ROOT = Path(__file__).resolve().parents[1]
EMAIL = "ahmadreza.smdi@gmail.com"
PROFILES = {
    "https://www.linkedin.com/in/ahmadreza-samadi/",
    "https://github.com/ahmadreza-smdi",
    "https://www.crunchbase.com/person/ahmadreza-samadi",
    "https://www.youtube.com/@ahmadreza-samadi",
    "https://www.instagram.com/ahmadreza.samadi/",
    "https://www.producthunt.com/@ahmadreza_samadi",
    "https://peerlist.io/ahmadrezasmdi",
    "https://dev.to/ahmadreza_smdi",
    "https://wellfound.com/u/ahmadreza-samadi",
    "https://www.threads.com/@ahmadreza.samadi",
}
ROLES = {
    "en": (("Co-Founder & Technical Lead",), ("Co-Founder & CEO",)),
    "fa": (("هم‌بنیان‌گذار و راهبر فنی",), ("هم‌بنیان‌گذار و مدیرعامل",)),
    "ar": (
        ("شريك مؤسس وقائد تقني", "شريكا مؤسسا وقائدا تقنيا"),
        ("شريك مؤسس ورئيس تنفيذي", "شريكا مؤسسا ورئيسا تنفيذيا"),
    ),
}
ARABIC = re.compile(
    r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]"
)
BAD_NAME = re.compile(
    r"\b(?:Ahmed\s*Samadi|Ahmedreza(?:\s*Samadi)?|Ahmadreza\s+Samady)\b|احمدرضا\s+صمد[ىي]ي|أحمدرضا\s+صمدى|احمدرضا\s+سمادی|أحمدرضا\s+سمادي",
    re.I,
)
HYPE = re.compile(
    r"\b(?:revolutionar(?:y|ies)|game[- ]changer|disrupt(?:ion|ive|ing)?|guru|unlock(?:s|ed|ing)?|10[x×]|secrets?|hacks?|I[’\x27]ve helped companies)\b|انقلابی|ثورة في|ثوري(?:ة)?|ده برابر|عشرة أضعاف",
    re.I,
)
RETIRED = re.compile(
    r"\b(?:I build|he builds|Samadi builds|building|my focus is|speciali[zs]es? in)\s+AI\s+for\s+(?:better\s+)?(?:property|real estate)\s+decisions|هوش مصنوعی برای (?:تصمیم[‌ ]های|تصمیم[‌ ]گیری) (?:بهتر )?(?:ملکی|املاک)|(?:أبني|يبني|أطوّر) الذكاء الاصطناعي (?:لتحسين |من أجل |لـ?)?(?:قرارات|لقرارات) (?:العقار|عقارية)",
    re.I,
)
MAIL = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
CONTACT = re.compile(
    r"(?:tel:\s*\+?\d|(?:\+971|00971)[\s(.-]*[2-9](?:[\s().-]*\d){7,8}\b|(?:phone|mobile|telephone|تلفن|هاتف)\s*[:：]\s*\+?[\d(][\d\s().-]{6,}|(?:office address|street address|نشانی دفتر|عنوان المكتب)\s*[:：]\s*\S+|\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,4}(?:Street|Road|Avenue|Boulevard)\b)",
    re.I,
)
RA = re.compile(r"Royal\s+Abraj|RAIA|رویال\s*ابراج|رويال\s*(?:أبراج|ابراج)", re.I)
BUILD = re.compile(r"Appraiva|اپرایوا|آپریوا|أبرايفا|أبريفا", re.I)
RA_DETAIL = re.compile(
    r"(?:[$€£]\s*\d|(?:USD|AED|EUR|درهم|دلار)\s*[\d۰-۹٠-٩]|[\d۰-۹٠-٩][\d.,٬٫]*\s*(?:dollars?|درهم|دلار)|(?:licen[cs]e|registration|ORN|رخصة|مجوز|ثبت تجاری|التسجيل)\s*(?:number|no\.?|رقم|شماره)?\s*[:#-]?\s*[A-Z-]*\d{3,}|\d[\d,٬.]*\s*(?:paying |active |فعال )?(?:customers?|clients?|مشتری|عملاء|عميلا)|\b(?:OpenAI|Anthropic|Gemini|GPT[- ]?\d|Claude|Azure|Bedrock|OpenRouter|Llama|Mistral|AWS|Google Cloud)\b|أوبن أي آي|آنتروپیک|أنتروبيك)",
    re.I,
)
ROLE_HINT = re.compile(
    r"\b(?:co[- ]?founder|founder|CEO|CTO|CFO|COO|technical lead|chief|director)\b|بنیان|مدیرعامل|\bمؤسس(?:ا)?\b|رئيس",
    re.I,
)
TRAIL_LABELS = {"Breadcrumb", "مسیر صفحه", "مسار الصفحة", "مسار التنقل"}


def language(path):
    return path.split("/")[0] if path.startswith(("fa/", "ar/")) else "en"


def normalized(s):
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
        ).split()
    )


def prohibited_link(u):
    p = urlsplit(urljoin(SITE, u))
    host = (p.hostname or "").lower().rstrip(".")
    return (
        host in ("x.com", "twitter.com", "t.co")
        or host.endswith((".twitter.com", ".x.com"))
        or (
            (host == "linkedin.com" or host.endswith(".linkedin.com"))
            and re.search(
                r"/(?:newsletters?|pulse/(?:[^/]+-)?newsletter)(?:/|$)", p.path, re.I
            )
        )
    )


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    field: str
    message: str
    fingerprint: str


def finding(rule, path, field, msg, value):
    return Finding(rule, path, field, msg, sha256(str(value).encode()).hexdigest())


def by_rules(
    path,
    field,
    text,
    lang,
    *,
    bio=False,
    english=False,
    contact=True,
    royal=False,
    identity=False,
):
    out = []

    def hit(rule, msg, val):
        out.append(finding(rule, path, field, msg, val))

    if BAD_NAME.search(text):
        hit("BR-NAME", "unapproved name spelling", text)
    if english and lang == "en" and ARABIC.search(text):
        hit("BR-SCRIPT", "non-English script in English identity or metadata", text)
    if bio or english:
        if HYPE.search(text):
            hit("BR-HYPE", "banned wording; check context", text)
    if bio and (
        RETIRED.search(text)
        or re.search(
            r"\bAI for (?:better )?(?:real estate|property) decisions\b", text, re.I
        )
    ):
        hit("BR-POSITIONING", "retired self-description", text)
    if bio:
        a, b = BUILD.search(text), RA.search(text)
        if a and b and a.start() > b.start():
            hit("BR-ROLE-ORDER", "operating company precedes Appraiva", text)
        if a and b and ROLE_HINT.search(text):
            role_lang = lang if lang != "en" and ARABIC.search(text) else "en"
            t = normalized(text)
            terms = [
                next(
                    (
                        normalized(label)
                        for label in spellings
                        if normalized(label) in t
                    ),
                    "",
                )
                for spellings in ROLES[role_lang]
            ]
            if not all(terms) or t.find(terms[0]) > t.find(terms[1]):
                hit(
                    "BR-ROLE-ORDER",
                    "expected both approved titles in builder/operator order",
                    text,
                )
    if contact:
        for email in set(MAIL.findall(text)):
            if email != EMAIL:
                hit("BR-EMAIL", "unapproved email address", email)
        if CONTACT.search(text):
            hit("BR-EMAIL", "possible phone number or office address", text)
    related = royal
    for sentence in re.split(r"(?<=[.!?؟])\s+|\n+", text):
        if RA.search(sentence):
            related = True
        elif re.search(r"Oxfam|\bMCI\b|Appraiva|أوكسفام|آکسفام", sentence, re.I):
            related = False
        public_fee = re.search(
            r"Dubai Land Department|\bDLD\b|دائرة الأراضي|اداره اراضی", sentence, re.I
        )
        operating = re.search(
            r"\b(?:RAIA|budget|vendor|our costs?|API)\b|بودجه|ميزانية", sentence, re.I
        )
        if related and RA_DETAIL.search(sentence) and (not public_fee or operating):
            hit("BR-RA-BLACKBOX", "possible private operating detail", sentence)
    return out


def graph_value(x):
    # Normalization from the November entity audit: list order is immaterial, references compare by @id.
    if isinstance(x, list):
        return tuple(sorted((graph_value(v) for v in x), key=repr))
    if isinstance(x, dict):
        if "@id" in x:
            return ("@id", x["@id"])
        return tuple(
            sorted((k, graph_value(v)) for k, v in x.items() if k != "@context")
        )
    return x


def expected_hubs(root):
    files = root / "locales"
    if not (files / "article-hubs.json").exists():
        return {}
    hubs = {
        h["id"]: h["paths"]
        for h in json.loads((files / "topic-hubs.json").read_text())["hubs"]
    }
    return {
        p: public_url(hubs[f["hub"]][loc])
        for f in json.loads((files / "article-hubs.json").read_text())["families"]
        for loc, p in f["paths"].items()
    }


def is_bio(e, path):
    if e.tag not in ("p", "dd", "li", "h1", "h2", "h3", "address", "div", "span"):
        return False
    if e.get("class") == "byline" and any(
        getattr(c, "tag", "") == "a" and "/topics/" in c.get("href") for c in e.children
    ):
        return False
    if e.tag in ("div", "span") and any(not isinstance(x, str) for x in e.children):
        return False
    classes = set(e.get("class").split())
    if classes & {
        "bio",
        "biography",
        "hero-statement",
        "hero-context",
        "local-author-bio",
    }:
        return True
    if e.within(
        lambda a: "article-author" in a.get("class").split() or a.get("id") == "bio-set"
    ):
        return True
    short = path.split("/")[-1]
    if short in ("about.html", "press.html") and (
        classes & {"lead", "byline", "localized-name"} or e.tag == "dd"
    ):
        return True
    return (
        e.within(lambda a: a.tag == "section" and a.get("id") == "about")
        and e.tag == "p"
    )


def validate_date(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?\+03:30", value
    ):
        return False
    try:
        return datetime.fromisoformat(value) <= datetime.now(timezone.utc)
    except ValueError:
        return False


def chronology_reversed(published, modified):
    try:
        a, b = datetime.fromisoformat(published), datetime.fromisoformat(modified)
        if not a.tzinfo or not b.tzinfo:
            return b.date() < a.date()
        return b < a
    except (ValueError, TypeError):
        return False


def inspect_page(path, raw, expected_hub=None):
    doc = Document(raw)
    url = public_url(path)
    lang = language(path)
    index = doc.indexable()
    snap = doc.snapshot(path)
    out = []

    def hit(rule, field, msg, value):
        out.append(finding(rule, path, field, msg, value))

    for field, text in [
        ("title", e.text())
        for e in doc.tags("title")
        if e.within(lambda a: a.tag == "head")
    ] + [
        (e.get("property") or e.get("name"), e.get("content"))
        for e in doc.tags("meta")
        if e.get("name") in ("description", "twitter:title", "twitter:description")
        or e.get("property").startswith("og:")
    ]:
        personal = re.sub(r"^(?:fa|ar)/", "", path) in (
            "index.html",
            "about.html",
            "press.html",
        )
        out += by_rules(
            path,
            field,
            text,
            lang,
            english=True,
            bio=personal
            and field
            in (
                "title",
                "description",
                "og:title",
                "og:description",
                "twitter:title",
                "twitter:description",
            ),
        )
    if index:
        for field, values, low, high in [
            (
                "title",
                [
                    e.text()
                    for e in doc.tags("title")
                    if e.within(lambda e: e.tag == "head")
                ],
                1,
                60,
            ),
            ("description", doc.meta("description"), 120, 165),
        ]:
            if len(values) != 1 or not low <= len(values[0]) <= high:
                hit(
                    "SEO-META",
                    field,
                    "missing, duplicated or outside the prescribed length",
                    values,
                )
        canonical = [e.get("href") for e in doc.links("canonical")]
        if canonical != [url]:
            hit(
                "SEO-META",
                "canonical",
                "expected one absolute self-canonical",
                canonical,
            )
    if lang not in ("en", "fa", "ar"):
        raise ValueError("unsupported language")
    royal_page = path.endswith("work/royal-abraj.html")
    for e in doc.elements:
        if e.tag in ("script", "style"):
            continue
        for literal in (s for s in e.children if isinstance(s, str) and "@" in s):
            for email in set(MAIL.findall(literal)):
                if email != EMAIL:
                    hit(
                        "BR-EMAIL",
                        "visible email",
                        "unapproved email in document text",
                        email,
                    )
        for name in ("href", "src", "action"):
            value = e.get(name)
            if value and prohibited_link(value):
                hit("BR-LINKS", name, "prohibited destination", value)
            if name == "href" and value.startswith(("mailto:", "tel:")):
                out += by_rules(path, "contact link", value, lang)
        if e.tag in (
            "p",
            "li",
            "dt",
            "dd",
            "h1",
            "h2",
            "h3",
            "address",
            "td",
            "figcaption",
            "a",
            "div",
            "span",
        ) and (
            e.tag not in ("span", "div")
            or not any(not isinstance(x, str) for x in e.children)
        ):
            text = e.text()
            if not text:
                continue
            bio = is_bio(e, path)
            if "article-author__name" in e.get("class").split():
                expected = {
                    "en": "Ahmadreza Samadi",
                    "fa": "احمدرضا صمدی",
                    "ar": "أحمدرضا صمدي",
                }[lang]
                if text != expected:
                    hit(
                        "BR-NAME",
                        "author box",
                        "unapproved localized author name",
                        text,
                    )
            out += by_rules(
                path,
                ("bio " if bio else "") + e.tag,
                text,
                lang,
                bio=bio,
                english=bio,
                royal=royal_page
                and e.within(lambda n: n.tag == "main")
                and not e.within(lambda n: n.tag in ("aside", "nav", "footer")),
            )
    for e in doc.tags("dl"):
        parts = [
            x for x in e.children if not isinstance(x, str) and x.tag in ("dt", "dd")
        ]
        if not parts or path.split("/")[-1] not in ("about.html", "press.html"):
            continue
        pairs = [
            (a.text(), b.text())
            for a, b in zip(parts, parts[1:])
            if a.tag == "dt" and b.tag == "dd"
        ]
        roles = [
            v
            for k, v in pairs
            if (BUILD.search(k) or RA.search(k)) and ROLE_HINT.search(v)
        ]
        if len(roles) >= 2:
            out += by_rules(
                path,
                "role table",
                " ".join(k + " " + v for k, v in pairs if v in roles),
                lang,
                bio=True,
            )
    for e in doc.elements:
        if e.tag == "time" and e.get("datetime"):
            value = e.get("datetime")
            if not validate_date(value):
                hit(
                    "SEO-DATES",
                    "visible datetime",
                    "invalid time, offset or future date",
                    value,
                )
        if e.tag == "meta" and e.get("property") in (
            "article:published_time",
            "article:modified_time",
        ):
            value = e.get("content")
            if not validate_date(value):
                hit(
                    "SEO-DATES",
                    e.get("property"),
                    "invalid time, offset or future date",
                    value,
                )
    graphs = []
    for i, block in enumerate(doc.blocks()):
        try:
            graphs.append(json.loads(block))
        except ValueError:
            hit("SEO-GRAPH", f"JSON-LD {i}", "invalid JSON-LD", block)
    allnodes = [n for g in graphs for n in nodes(g)]
    if path in (
        "about.html",
        "index.html",
        "fa/about.html",
        "fa/index.html",
        "ar/about.html",
        "ar/index.html",
    ) and any(
        n.get("@type") in ("AboutPage", "ProfilePage", "WebSite") for n in allnodes
    ):
        full = [
            n
            for n in allnodes
            if n.get("@id") == SITE + "#person"
            and n.get("@type") == "Person"
            and "sameAs" in n
        ]
        if not full:
            hit(
                "BR-LINKS",
                "primary Person",
                "expected a full profile set on the identity page",
                path,
            )
    for n in allnodes:
        kind = n.get("@type")
        identifier = n.get("@id", "")
        for key in ("telephone", "streetAddress", "faxNumber"):
            if n.get(key):
                hit(
                    "BR-EMAIL",
                    "JSON-LD " + key,
                    "private contact field in structured data",
                    n[key],
                )
        for field, v in n.items():
            if not isinstance(v, str):
                continue
            out += by_rules(
                path,
                "JSON-LD " + field,
                v,
                lang,
                english=field == "description",
                bio=kind == "Person" and field == "description",
            )
            if v.startswith(("https://", "http://", "//")) and prohibited_link(v):
                hit("BR-LINKS", "JSON-LD " + field, "prohibited destination", v)
        for k, v in n.items():
            if isinstance(v, list):
                for val in v:
                    if (
                        isinstance(val, str)
                        and val.startswith(("https://", "http://", "//"))
                        and prohibited_link(val)
                    ):
                        hit("BR-LINKS", "JSON-LD " + k, "prohibited destination", val)
        if kind == "Person":
            for field in ("name", "givenName", "familyName", "alternateName"):
                if (
                    field in n
                    and {
                        "name": "Ahmadreza Samadi",
                        "givenName": "Ahmadreza",
                        "familyName": "Samadi",
                        "alternateName": ["Ahmad Samadi"],
                    }[field]
                    != n[field]
                    and identifier == SITE + "#person"
                ):
                    hit(
                        "BR-NAME",
                        "Person " + field,
                        "personal identity differs from the approved value",
                        n[field],
                    )
            if "sameAs" in n or (
                identifier == SITE + "#person" and ("jobTitle" in n or "givenName" in n)
            ):
                value = n.get("sameAs", [])
                if not isinstance(value, list) or sorted(value) != sorted(PROFILES):
                    hit(
                        "BR-LINKS",
                        "Person sameAs",
                        "approved profile set changed",
                        value,
                    )
            if "jobTitle" in n and n["jobTitle"] != [
                "Co-Founder & Technical Lead, Appraiva",
                "Co-Founder & CEO, Royal Abraj Group",
            ]:
                hit(
                    "BR-ROLE-ORDER",
                    "Person jobTitle",
                    "approved titles or order changed",
                    n["jobTitle"],
                )
            if (
                "worksFor" in n
                and isinstance(n["worksFor"], list)
                and identifier == SITE + "#person"
            ):
                wanted = [
                    ("Co-Founder & Technical Lead", SITE + "#appraiva"),
                    ("Co-Founder & CEO", SITE + "#royal-abraj"),
                ]
                actual = [
                    (v.get("roleName"), v.get("worksFor", {}).get("@id"))
                    for v in n["worksFor"]
                    if isinstance(v, dict)
                ]
                if actual != wanted:
                    hit(
                        "BR-ROLE-ORDER",
                        "Person worksFor",
                        "role-to-company assignment changed",
                        actual,
                    )
        for key in ("datePublished", "dateModified", "dateCreated", "uploadDate"):
            if key in n and not validate_date(n[key]):
                hit("SEO-DATES", key, "invalid time, offset or future date", n[key])
        if (
            n.get("dateModified")
            and n.get("datePublished")
            and chronology_reversed(n["datePublished"], n["dateModified"])
        ):
            hit(
                "SEO-DATES",
                "chronology",
                "modified before publication",
                n["dateModified"],
            )
    signed = [
        n.get("itemListElement") for n in allnodes if n.get("@type") == "BreadcrumbList"
    ]
    trail = visible_trail(raw, url)
    if signed != ([trail] if trail else []):
        hit(
            "SEO-BREADCRUMB",
            "visible and structured trail",
            "visible and JSON-LD paths differ",
            [trail, signed],
        )
    if expected_hub and (not trail or trail[-1]["item"] != expected_hub):
        hit(
            "SEO-BREADCRUMB",
            "primary hub",
            "article trail has the wrong final hub",
            trail,
        )
    if (
        path.split("/")[-2:-1] == ["writing"]
        and not path.endswith("/index.html")
        and any(v["name"] in snap["h1"] for v in trail)
    ):
        hit(
            "SEO-BREADCRUMB",
            "headline",
            "article headline repeated in navigation",
            trail,
        )
    alts = {}
    for e in doc.links("alternate"):
        code = e.get("hreflang")
        if code:
            if code in alts:
                hit("SEO-HREFLANG", code, "duplicate language alternate", code)
            alts[code] = e.get("href")
    return snap, index, alts, allnodes, out


def document_findings(path, text):
    results = []

    def hit(rule, field, msg, value):
        results.append(finding(rule, path, field, msg, value))

    for email in set(MAIL.findall(text)) if "@" in text else ():
        if email != EMAIL:
            hit("BR-EMAIL", "download email", "unapproved email in file", email)
    profile = "profile/" in path and (
        "-facts.pdf" in path or "-bio.txt" in path or path.endswith(".vcf")
    )
    llms = path.startswith("llms")
    if profile or llms:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Catalogue entries are article subjects. The quoted introduction and fact lines are biography.
            intro = profile or line.startswith(
                ("> ", "- Position:", "- Co-Founder", "Ahmadreza Samadi is")
            )
            results += by_rules(
                path,
                "biography line" if intro else "catalogue line",
                line,
                "en",
                bio=intro,
                english=intro,
            )
        if path.endswith(".vcf"):
            fields = dict(
                line.split(":", 1) for line in text.splitlines() if ":" in line
            )
            if (
                fields.get("ORG") != "Appraiva / Royal Abraj Group"
                or fields.get("TITLE")
                != "Co-Founder & Technical Lead / Co-Founder & CEO"
            ):
                hit(
                    "BR-ROLE-ORDER",
                    "vCard",
                    "vCard organizations and role titles must correspond",
                    [fields.get("ORG"), fields.get("TITLE")],
                )
            if (
                fields.get("FN") != "Ahmadreza Samadi"
                or fields.get("NICKNAME") != "Ahmad Samadi"
            ):
                hit(
                    "BR-NAME",
                    "vCard",
                    "incorrect name or nickname",
                    [fields.get("FN"), fields.get("NICKNAME")],
                )
            if any(k.split(";")[0] in ("TEL", "ADR") for k in fields):
                hit("BR-EMAIL", "vCard", "private contact field in card", "ADR or TEL")
        elif "-bio.txt" in path or llms:
            # Check the joint organization order even when titles/companies occupy successive lines.
            heading = (
                text.split("SHORT BIOGRAPHY")[0]
                if "-bio.txt" in path
                else "\n".join(
                    l for l in text.splitlines() if l.startswith("- Co-Founder")
                )
            )
            if heading:
                results += by_rules(path, "role sequence", heading, "en", bio=True)
    for u in (
        re.findall(r'https?://[^\s<>"\])]+', text)
        if ("twitter." in text or "x.com" in text or "linkedin." in text)
        else ()
    ):
        if prohibited_link(u):
            hit("BR-LINKS", "download URL", "prohibited destination", u)
    return results


def audit(root, baseline, with_downloads=True):
    from brand_downloads import downloads, documents

    hubs = expected_hubs(root)
    snapshots = {}
    alternates = {}
    indexed = set()
    allurls = {}
    out = []
    declarations = defaultdict(lambda: defaultdict(dict))
    unique = defaultdict(list)
    for p in pages(root):
        path = p.relative_to(root).as_posix()
        snapshot, index, alts, graph, issues = inspect_page(
            path, p.read_text(encoding="utf-8"), hubs.get(path)
        )
        out += issues
        url = public_url(path)
        allurls[url] = path
        alternates[url] = alts
        if path in hubs:
            snapshot["primary_hub"] = hubs[path]
            if (
                baseline is not None
                and path in baseline
                and baseline[path].get("primary_hub") is not None
                and baseline[path]["primary_hub"] != hubs[path]
            ):
                out.append(
                    finding(
                        "SEO-BREADCRUMB",
                        path,
                        "reviewed primary hub",
                        "primary hub differs from the reviewed assignment",
                        hubs[path],
                    )
                )
        if index:
            indexed.add(url)
            snapshots[path] = snapshot
            for k in ("title", "description"):
                if snapshot[k]:
                    unique[k, snapshot[k].casefold()].append(path)
        for n in graph:
            if not n.get("@id") or len(n) == 1:
                continue
            for k, v in n.items():
                if k in ("@id", "@context", "@graph"):
                    continue
                declarations[n["@id"]][k].setdefault(repr(graph_value(v)), set()).add(
                    path
                )
    for (field, value), paths in unique.items():
        if len(paths) > 1:
            for path in paths:
                out.append(
                    finding(
                        "SEO-META",
                        path,
                        field,
                        "duplicate across indexable pages",
                        value,
                    )
                )
    for ident, props in declarations.items():
        for k, variants in props.items():
            if len(variants) > 1:
                for path in set.union(*variants.values()):
                    out.append(
                        finding(
                            "SEO-GRAPH",
                            path,
                            k,
                            "conflicting declarations for " + ident,
                            sorted(variants),
                        )
                    )
    for origin, links in alternates.items():
        path = allurls[origin]
        short = re.sub(r"^(?:fa|ar)/", "", path)
        editions = {
            l: public_url(prefix + short)
            for l, prefix in [("en", ""), ("fa", "fa/"), ("ar", "ar/")]
            if public_url(prefix + short) in indexed
        }
        if origin in indexed and len(editions) > 1:
            expected = {**editions, "x-default": editions.get("en", origin)}
            if links != expected:
                out.append(
                    finding(
                        "SEO-HREFLANG",
                        path,
                        "cluster membership",
                        "missing, incorrect or duplicated language member",
                        links,
                    )
                )
        for code, target in links.items():
            if target not in indexed or alternates.get(target) != links:
                out.append(
                    finding(
                        "SEO-HREFLANG",
                        path,
                        code,
                        "target absent, non-indexable or not reciprocal",
                        target,
                    )
                )
    sm = root / "sitemap.xml"
    site_map = ElementTree.parse(sm)
    urls = [n.text for n in site_map.findall("{*}url/{*}loc")]
    for u in sorted(indexed.symmetric_difference(urls)):
        out.append(
            finding(
                "SEO-SITEMAP",
                allurls.get(u, "sitemap.xml"),
                "loc",
                "sitemap and indexable pages differ",
                u,
            )
        )
    if len(set(urls)) != len(urls):
        out.append(
            finding(
                "SEO-SITEMAP", "sitemap.xml", "loc", "duplicate URL in sitemap", urls
            )
        )
    for item in site_map.findall("{*}url"):
        mod = item.findtext("{*}lastmod")
        if mod:
            try:
                if len(mod) == 10:
                    good = (
                        datetime.fromisoformat(mod).date()
                        <= datetime.now(timezone.utc).date()
                    )
                else:
                    good = validate_date(mod)
            except ValueError:
                good = False
            if not good:
                out.append(
                    finding(
                        "SEO-DATES",
                        allurls.get(item.findtext("{*}loc"), "sitemap.xml"),
                        "lastmod",
                        "unexpected or future sitemap date",
                        mod,
                    )
                )
    if with_downloads:
        for path, p in downloads(root):
            try:
                for name, text in documents(path, p.read_bytes()):
                    out += document_findings(name, text)
            except Exception as exc:
                out.append(
                    finding(
                        "BR-EMAIL",
                        path,
                        "download inspection",
                        "document could not be checked: " + type(exc).__name__,
                        path,
                    )
                )
    if baseline is not None:
        for path in sorted(set(baseline) | set(snapshots)):
            old, new = baseline.get(path, {}), snapshots.get(path, {})
            fields = [
                k
                for k in ("title", "description", "canonical", "h1", "jsonld_sha256")
                if old.get(k) != new.get(k)
            ]
            if fields:
                out.append(
                    finding(
                        "SEO-FREEZE",
                        path,
                        ",".join(fields),
                        "public metadata changed",
                        new,
                    )
                )
    return snapshots, sorted(
        set(out), key=lambda r: (r.rule, r.path, r.field, r.fingerprint)
    )


def review(issues, allow):
    keys = {}
    for item in allow:
        key = tuple(item[k] for k in ("rule", "path", "field", "fingerprint"))
        if (
            key in keys
            or any("*" in v for v in key[:3])
            or not re.fullmatch("[0-9a-f]{64}", key[3])
            or not item["reason"].strip()
        ):
            raise ValueError("invalid or duplicate narrow allowlist entry")
        keys[key] = item["reason"]
    records = []
    used = set()
    for r in issues:
        key = (r.rule, r.path, r.field, r.fingerprint)
        reason = keys.get(key, "")
        if reason:
            used.add(key)
        records.append(
            dict(
                **asdict(r),
                status="WARN"
                if r.rule == "SEO-FREEZE"
                else "ALLOW"
                if reason
                else "FAIL",
                reason=reason,
            )
        )
    for key in keys.keys() - used:
        records.append(
            dict(
                rule=key[0],
                path=key[1],
                field=key[2],
                fingerprint=key[3],
                message="stale allowlist entry",
                status="FAIL",
                reason=keys[key],
            )
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    baseline = json.loads((args.root / "data/seo-baseline.json").read_text())
    allow = json.loads((args.root / "scripts/brand-allowlist.json").read_text())
    pageset, issues = audit(args.root, baseline)
    records = review(issues, allow)
    if args.csv:
        with args.csv.open("w", newline="") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=[
                    "rule",
                    "path",
                    "field",
                    "message",
                    "fingerprint",
                    "status",
                    "reason",
                ],
            )
            w.writeheader()
            w.writerows(records)
    for item in records:
        if item["status"] in ("WARN", "FAIL"):
            print(
                item["status"],
                item["rule"],
                item["path"],
                item["field"],
                item["message"],
            )
    fail = sum(r["status"] == "FAIL" for r in records)
    print(
        f"{'FAIL' if fail else 'PASS'} brand and SEO: {len(pageset)} indexable pages, {fail} failures, {sum(r['status'] == 'WARN' for r in records)} drift warnings, {sum(r['status'] == 'ALLOW' for r in records)} reviewed exceptions"
    )
    return int(bool(fail))


if __name__ == "__main__":
    sys.exit(main())
