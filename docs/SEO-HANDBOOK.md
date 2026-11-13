# How this website reaches search and AI readers

The public identity begins with a Dubai technology entrepreneur who builds AI and runs a business. Appraiva and Royal Abraj supply the two concrete roles. Edit the identity source in `locales/brand-layer.json` and run its generators. The visible biography, the Person description and the first-person summary in the two machine catalogues have different audiences. Use the approved brand foundation and retain the company facts.

The sitemap lists indexable pages. Each translated family points to its own canonical editions and to the English default. Persian and Arabic have their own entry URLs. Article navigation draws on the reviewed topic and related-link configuration. Studies, tools, films and articles can describe property in their own terms.

## Verify a change

Run `python3 scripts/check_all.py`. The manual runner discovers each local checker, generator check and fixture. A generator check reports stale output. The brand checks protect names, roles, evidence boundaries, identity order, links and the metadata comparison. The link and locale checks validate destinations, fragments, alternate groups, local click depth, text direction and Persian characters. All regular images need positive width and height. The initial first-party byte budget counts local HTML, CSS and its referenced assets, scripts, fonts, eager images and posters. The data explorer has its own measured allowance. The budget is an offline regression check. Browser timing and accessibility still need a browser measurement.

Film, study, source, date and build checks protect structured data and public evidence. The publish-tree builder combines sitemaps, public links, dependencies and reviewed compatibility paths. The private measurement exports and this handbook stay outside the website tree. Previously published compatibility files remain on the site branch until the owner decides their disposition.

## Publish or restore

1. Run the full local suite. Review the changed files and commit only the intended work. Pull with `git pull --ff-only` and push the source branch `main`.
2. Run `python3 scripts/publish.py --dry-run`. Compare the public path set and byte changes with the intended release.
3. Run `python3 scripts/publish.py`, review its printed command and execute that command. Pages serves the repository’s `site` branch at the root.
4. Run `python3 scripts/check_all.py --live` and check the cache-busted changed URLs. If a release breaks a public URL, restore the last tree first with `python3 scripts/publish.py --rollback` and its printed command. Verify the restored site before repairing and republishing.

## November measurement

Through 8 December 2026 the search-result text, visible copy, titles, headings, URLs, bios, topic assignments, breadcrumbs, artwork and layout are frozen. Preserve the baseline so the pre/post Search Console comparison remains interpretable. Record visible editorial proposals privately for the owner after the window. The owner repeats the assistant test on 1 February 2027.

**In-app accessibility check (manual, offline).** Use the local `axe.min.js` from axe-core 4.10.3; the checker verifies the pinned file hash. Run `python3 scripts/check_axe_iab.py --serve-local /path/to/axe.min.js`, open its loopback URL in the in-app browser, click **Run the template checks**, and save the receipt outside the repo. Stop the temporary server. Run `WEBSITE_AXE_RECEIPT=/private/axe-iab-receipt.json python3 scripts/check_all.py`. A changed site input or missing sample invalidates the receipt. Without a receipt the check reports SKIP. Review incomplete rules and keyboard behaviour separately.

## AI answers

Run `python3 scripts/build_answer_resources.py` and `python3 scripts/build_llms.py` after editing a reviewed source page. The manual release checks discover the following checks and failing fixtures automatically.

- Catalogue text and public passages must reproduce from the published HTML.
- Thirty main-content Markdown companions must match their HTML and each must have one head discovery link. The three biographies, three Royal Abraj case pages and the founder essay omit operator material outside the approved public scope.
- Typed declarations of the owner must share one Person ID, identifying description and named portrait. Bare ID references resolve to that entity.
- Sitemap modification times cannot follow the latest Git commit for the associated page. The reviewed page revisions identify meaningful source changes independently of the build clock. Editorial publication and film upload dates retain their original meanings.
- Raw HTML must retain the previously measured identity facts for each template and language. Utility and verification endpoints have different content requirements.
- The repository's 19 declared crawler-policy expectations and content signals are checked offline. The served edge policy needs a separate live comparison.

The Markdown companions are outside the sitemap. GitHub Pages serves static files from the site branch with Jekyll disabled. A Markdown body cannot set an HTTP robots header. Treat the HTML URL as canonical in discovery and review any HTTP header policy separately.
