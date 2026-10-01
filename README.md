# Ahmadreza Samadi — personal website

Source for [a-samadi.com](https://a-samadi.com/), the personal website of Ahmadreza Samadi: Co-Founder & Technical Lead at Appraiva and Co-Founder & CEO at Royal Abraj Group, based in Dubai.

The site brings together my professional biography, selected work, writing on AI products and data systems, and an interactive decision guide. English is the primary language, with separate Persian and Arabic pages.

## Explore the work

- [Appraiva: turning property imagery into decision support](https://a-samadi.com/work/appraiva.html) — my work on AI real estate intelligence as Co-Founder & Technical Lead.
- [Royal Abraj Group: digital strategy and operations](https://a-samadi.com/work/royal-abraj.html) — connecting websites, CRM, customer tools and internal workflows.
- [Oxfam Novib: a data foundation for CRM and analytics](https://a-samadi.com/work/oxfam-novib.html) — Azure data engineering for migration, governance and reporting.

These case studies describe my contributions to company and client projects; this repository contains the personal website source.

## Read and try

- [Before You Build the AI](https://a-samadi.com/tools/before-you-build-ai.html) — an interactive field guide for defining a decision, reviewing its evidence and planning a first experiment. The worksheet runs in the browser and supports text export and printing.
- [English writing](https://a-samadi.com/writing/) — essays on AI products, data and PropTech.
- [English RSS feed](https://a-samadi.com/writing/feed.xml) — article summaries linking to the original essays.
- [Biography and official profiles](https://a-samadi.com/about.html) · [Get in touch](https://a-samadi.com/#contact).

## Preview locally

The site uses static HTML, CSS and JavaScript. From the repository root, start a local server with Python 3:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open [localhost:8000](http://localhost:8000/). No build step is required to preview the checked-in site.

## Maintain the source

Run these existing checks from the repository root with Python 3 and Node.js:

```sh
python3 scripts/check_locale_parity.py
node scripts/check_guide_locales.mjs
python3 scripts/build_feed.py --check
```

The checks cover language and canonical metadata, author identity, localized guide behavior and exports, and RSS consistency.

| When changing | Source and regeneration command |
| --- | --- |
| Shared styles | Edit `css/premium.css`, `css/editorial.css` and `css/refinement.css`; run `python3 scripts/build_styles.py`. |
| Homepages | Edit `index.html` and translations in `locales/fa.json` and `locales/ar.json`; run `python3 scripts/build_locales.py`. |
| Interactive guide | Edit the English guide and `js/decision-guide.js`, plus `locales/decision-guide-fa.json` and `locales/decision-guide-ar.json`; run `python3 scripts/build_guide_locales.py`. |
| English writing feed | Edit the articles' metadata; run `python3 scripts/build_feed.py`. Keep original publication dates and include the existing RSS discovery link in new English articles. |

Review generated changes and run the checks before publishing. Keep English as the primary entry point, preserve Persian and Arabic URLs, and retain the site's motion controls and reduced-motion support.
