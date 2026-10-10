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

## Try the property-research example

Open the [live English guide](https://a-samadi.com/tools/before-you-build-ai.html) with JavaScript enabled. **Property research** loads automatically and builds an illustrative brief. You can reload it with the **Property research** button; **Support triage** loads another example, and **Start empty** clears the worksheet.

The property example asks which properties deserve closer investigation before an investor commits more time. Its next action is a shortlist followed by requests for missing information or a manual inspection. The initial selections are:

- Evidence: **Some is available; gaps remain**.
- Consequences: **It creates meaningful rework or cost**.
- Review: **A person reviews every result**.

The default **Resolve first** section begins:

> Make the gaps visible. Identify missing sources and define when the tool must ask for information or hand the decision back to a person.

Try changing **Who reviews before action?** to **No review is planned**. Both **Export .txt** and **Print / save PDF** become disabled when an input changes. Click **Build my decision brief** to rebuild from the completed fields; the brief now recommends adding a review step, and export/print become available again.

Export before leaving: worksheet entries stay in page memory. This is a structured thinking aid with illustrative scenarios, not customer results or a validated assessment. The [worksheet logic](js/decision-guide.js) turns the selected evidence, consequences and review choices into guidance; it does not validate the supplied evidence.

Inspect the [English page source](tools/before-you-build-ai.html) alongside the worksheet logic.

## Preview locally

The site uses static HTML, CSS and JavaScript. From the repository root, start a local server with Python 3:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open [localhost:8000](http://localhost:8000/). No build step is required to preview the checked-in site.

The interface uses its own system, Lagoon: a pale mist canvas, deep sea-ink type, pastel mint and sky for surfaces and light, and one lagoon teal for links and actions. Quiet land contours (`assets/img/contours.svg`) sit behind the homepage hero and the top of each reading page, a nod to property and land data. Sora sets names, headings and controls; running Latin text uses the reader's system font; Persian and Arabic text uses Vazirmatn. The web fonts are self-hosted in `assets/fonts/` under the SIL Open Font License (`assets/fonts/OFL.txt`).

`js/future.js` adds the homepage behavior: the Dubai clock, the Ask panel (⌘K / Ctrl K, `/` or any Ask button) that searches the page and streams back the best passage, the portrait frame (a scan passes over it when the page opens and when the pointer arrives, and it leans toward the pointer), the living terrain behind the hero (a canvas of shifting contour lines with data points flowing along them, a rise under the pointer, a ripple from the portrait scan and from taps on touch screens; it falls back to the static contours), pointer light on cards and the name, section names that resolve from scrambled characters, the floating Ask button, and the Appraiva console run. All pages use cross-document view transitions, and section survey lines draw with scroll where the browser supports scroll-driven animation. Every effect follows the page's pause control, stops when its part of the page is off screen or the tab is hidden, and honors reduced-motion preferences; without JavaScript the page is complete and static. Reading pages share the same tokens through CSS only.

## Maintain the source

Run these existing checks from the repository root with Python 3 and Node.js:

```sh
python3 scripts/check_locale_parity.py
python3 scripts/check_internal_links.py
node scripts/check_guide_locales.mjs
python3 scripts/build_feed.py --check
python3 scripts/enrich_metadata.py --check
python3 scripts/build_llms.py --check
```

The checks cover language and canonical metadata, author identity, same-site page and fragment links, localized guide behavior and exports, RSS consistency, and the social and search metadata every page carries in its own language.

| When changing | Source and regeneration command |
| --- | --- |
| Shared styles | Edit `css/premium.css`, `css/editorial.css` and `css/refinement.css`; run `python3 scripts/build_styles.py`. |
| Homepages | Edit `index.html` and translations in `locales/fa.json` and `locales/ar.json`; run `python3 scripts/build_locales.py`. |
| Interactive guide | Edit the English guide and `js/decision-guide.js`, plus `locales/decision-guide-fa.json` and `locales/decision-guide-ar.json`; run `python3 scripts/build_guide_locales.py`. |
| Page metadata and sitemap languages | Run `python3 scripts/enrich_metadata.py` after adding or translating a page. It fills in missing Open Graph, Twitter and robots tags in the page's language, the sitemap's hreflang links and the structured-data links that mark English pages as the originals (`workTranslation`) and Persian and Arabic pages as their translations (`translationOfWork`); then regenerate the homepages and guide. |
| AI assistant map | Run `python3 scripts/build_llms.py` after adding or retitling pages. It rewrites `llms.txt` from the sitemap and each page's title and description, English first. |
| English writing feed | Edit the articles' metadata; run `python3 scripts/build_feed.py`. Keep original publication dates and include the existing RSS discovery link in new English articles. |

Review generated changes and run the checks before publishing. Keep English as the primary entry point, preserve Persian and Arabic URLs, and retain the site's motion controls and reduced-motion support.
