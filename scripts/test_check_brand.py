"""Offline negative controls. Every rule must identify its own change on an otherwise passing page."""

import json
from pathlib import Path
import tempfile
import unittest
from check_brand import audit, review, inspect_page, document_findings, PROFILES
from seo_document import public_url

FIXTURES = Path(__file__).with_name("fixtures") / "brand"
RULES = set(
    "BR-ROLE-ORDER BR-NAME BR-SCRIPT BR-HYPE BR-LINKS BR-EMAIL BR-RA-BLACKBOX BR-POSITIONING SEO-META SEO-HREFLANG SEO-SITEMAP SEO-DATES SEO-GRAPH SEO-BREADCRUMB SEO-FREEZE".split()
)
DESC = "A prepared example gives the reviewer enough information to identify the document, understand its purpose and decide whether the public text is accurate."


def markup(path, lang, head="", body="", description=DESC, h1="Fixture"):
    return (
        f'<html lang="{lang}"><head><title>Example {lang}</title><meta name="description" content="{description}">'
        f'<link rel="canonical" href="{public_url(path)}">{head}</head><body><main><h1>{h1}</h1>{body}</main></body></html>'
    )


def sitemap(root, urls, extra=""):
    (root / "sitemap.xml").write_text(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join("<url><loc>" + u + "</loc></url>" for u in urls)
        + extra
        + "</urlset>"
    )


def graph(data):
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script>"
    )


class BrandRules(unittest.TestCase):
    def test_fixtures(self):
        seen = set()
        for f in sorted(FIXTURES.glob("*.json")):
            record = json.loads(f.read_text())
            rule = record["rule"]
            seen.add(rule)
            self.assertEqual(set(record["cases"]), {"en", "fa", "ar"})
            for loc, value in record["cases"].items():
                with (
                    self.subTest(rule=rule, language=loc),
                    tempfile.TemporaryDirectory() as folder,
                ):
                    root = Path(folder)
                    placement = record["placement"]
                    lang = "en" if placement == "english_head" else loc
                    path = ("" if lang == "en" else lang + "/") + "index.html"
                    p = root / path
                    p.parent.mkdir(exist_ok=True)
                    p.write_text(markup(path, lang))
                    sitemap(root, [public_url(path)])
                    snapshot, clean = audit(root, None, False)
                    self.assertEqual(clean, [])
                    if placement == "sitemap":
                        sitemap(root, [public_url(path)], value)
                    else:
                        p.write_text(
                            markup(
                                path,
                                lang,
                                **{
                                    (
                                        "head"
                                        if placement == "english_head"
                                        else placement
                                    ): value
                                },
                            )
                        )
                    _, hits = audit(
                        root, snapshot if rule == "SEO-FREEZE" else None, False
                    )
                    self.assertEqual({x.rule for x in hits}, {rule})
                    disposition = review(hits, [])
                    self.assertTrue(
                        all(
                            x["status"] == ("WARN" if rule == "SEO-FREEZE" else "FAIL")
                            for x in disposition
                        )
                    )
        self.assertEqual(seen, RULES)

    def test_exact_roles_in_all_languages(self):
        for loc, text in [
            (
                "en",
                "Co-Founder & CTO of Appraiva and Co-Founder & CEO of Royal Abraj Group",
            ),
            ("fa", "مدیر فنی Appraiva و هم‌بنیان‌گذار و مدیرعامل Royal Abraj Group"),
            ("ar", "مدير Appraiva وشريك مؤسس ورئيس تنفيذي في Royal Abraj Group"),
        ]:
            path = loc + "/about.html" if loc != "en" else "about.html"
            self.assertIn(
                "BR-ROLE-ORDER",
                {
                    x.rule
                    for x in inspect_page(
                        path, markup(path, loc, body='<p class="bio">' + text + "</p>")
                    )[-1]
                },
            )

    def test_sameas_and_canonical(self):
        for profiles in [
            [],
            sorted(PROFILES)[:-1],
            sorted(PROFILES) + [next(iter(PROFILES))],
        ]:
            head = graph(
                {
                    "@id": "https://a-samadi.com/#person",
                    "@type": "Person",
                    "sameAs": profiles,
                }
            )
            h = inspect_page("index.html", markup("index.html", "en", head=head))[-1]
            self.assertIn("BR-LINKS", {r.rule for r in h})
        for change in ["<title>Second</title>", '<link rel="canonical" href="/"/>']:
            self.assertIn(
                "SEO-META",
                {
                    h.rule
                    for h in inspect_page(
                        "index.html", markup("index.html", "en", head=change)
                    )[-1]
                },
            )

    def test_approved_language_and_context(self):
        body = '<p>Face ID can unlock the phone.</p><p>Dubai Land Department charges AED 250. Royal Abraj is named for context.</p><a href="/topics/ai-real-estate.html">AI for property decisions</a>'
        self.assertFalse(
            inspect_page("index.html", markup("index.html", "en", body=body))[-1]
        )
        for lang, text in [
            ("fa", "اطلاعات درباره فناوری"),
            ("ar", "معلومات عن التقنية"),
        ]:
            path = lang + "/about.html"
            self.assertFalse(
                inspect_page(
                    path, markup(path, lang, body='<p class="bio">' + text + "</p>")
                )[-1]
            )

    def test_local_contacts_and_vcard(self):
        self.assertIn(
            "BR-EMAIL",
            {
                r.rule
                for r in document_findings(
                    "assets/profile/example.vcf",
                    "FN:Ahmadreza Samadi\nTEL:+12025550100",
                )
            },
        )
        self.assertIn(
            "BR-ROLE-ORDER",
            {
                r.rule
                for r in document_findings(
                    "assets/profile/example.vcf", "ORG:Royal Abraj Group / Appraiva"
                )
            },
        )
        for text in [
            "RAIA uses Claude.",
            "RAIA has 52 customers.",
            "RAIA registration number TEST1234.",
        ]:
            self.assertIn(
                "BR-RA-BLACKBOX",
                {
                    r.rule
                    for r in inspect_page(
                        "index.html",
                        markup("index.html", "en", body="<p>" + text + "</p>"),
                    )[-1]
                },
            )

    def test_exact_exception_does_not_apply_to_changed_copy(self):
        p = "index.html"

        def issues(text):
            return inspect_page(
                p, markup(p, "en", body='<p class="bio">' + text + "</p>")
            )[-1]

        original = issues("A revolutionary example")
        r = original[0]
        allow = [
            dict(
                rule=r.rule,
                path=r.path,
                field=r.field,
                fingerprint=r.fingerprint,
                reason="specific test exception",
            )
        ]
        self.assertEqual(review(original, allow)[0]["status"], "ALLOW")
        self.assertTrue(
            all(
                q["status"] == "FAIL"
                for q in review(issues("A revolutionary example again"), allow)
            )
        )
        with self.assertRaises(ValueError):
            review(original, [{**allow[0], "path": "*"}])

    def test_primary_hub_and_duplicate_metadata_and_reciprocity(self):
        head = graph(
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Hub",
                        "item": "https://a-samadi.com/wrong/",
                    }
                ],
            }
        )
        body = '<nav aria-label="Breadcrumb"><a href="/wrong/">Hub</a></nav>'
        h = inspect_page(
            "writing/sample.html",
            markup("writing/sample.html", "en", head=head, body=body),
            "https://a-samadi.com/right/",
        )[-1]
        self.assertIn("SEO-BREADCRUMB", {r.rule for r in h})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "fa").mkdir()
            names = ["index.html", "fa/index.html"]
            sitemap(root, map(public_url, names))
            for path in names:
                (root / path).write_text(markup(path, "en"))
            _, hits = audit(root, None, False)
            self.assertEqual({r.rule for r in hits}, {"SEO-HREFLANG", "SEO-META"})


if __name__ == "__main__":
    unittest.main()
