"""Keep versioned study identity and reuse notes separate from code licensing.

The licence is scoped to original study contributions; government inputs, code,
fonts and identity assets retain their existing status. Mixed input periods and
full CSV field definitions remain explicit. No measurements are recomputed.
"""
from pathlib import Path
import csv
from html import escape
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
STUDIES = {
    'studies/rent-own-2026/index.html': (
        'https://github.com/ahmadreza-smdi/rent-own-metro-study/releases/tag/v1.0.0',
        'https://github.com/ahmadreza-smdi/rent-own-metro-study/blob/7eacdc415794290a30d09d9eccb0e1f03b2b4601/data-notes.md',
    ),
    'studies/rent-burden/index.html': (
        'https://github.com/ahmadreza-smdi/metro-rent-burden/releases/tag/v1.1.1',
        'https://github.com/ahmadreza-smdi/metro-rent-burden/blob/9525742e49956e51fe5ac72c9ef3000624af4401/README.md#reuse-and-citation',
    ),
}

# Column definitions are self-contained; the build never reads private workspace files.
FIELD_DEFINITIONS = json.loads(r'''{
  "rent-own-2026": {
    "acs_year": {
      "name": "ACS observation year",
      "description": "Calendar year of the ACS one-year owner-stock source.",
      "unitText": "year"
    },
    "annual_cash_surplus": {
      "name": "Illustrative annual cash surplus",
      "description": "Receipts minus management, fixed budget and principal/interest; not an investment return.",
      "unitText": "USD per year"
    },
    "annual_fixed_budget": {
      "name": "Illustrative annual fixed budget",
      "description": "Property tax, insurance, maintenance reserve, 12 monthly HOA payments, other annual costs and mortgage insurance; excludes management and principal/interest.",
      "unitText": "USD per year"
    },
    "annual_insurance": {
      "name": "Illustrative annual property insurance",
      "description": "Owner-stock value proxy multiplied by the assumed insurance fraction.",
      "unitText": "USD per year"
    },
    "annual_interest_rate": {
      "name": "Assumed fixed annual interest rate",
      "description": "Scenario input expressed as a 0–1 fraction, not a percentage number.",
      "unitText": "fraction"
    },
    "annual_maintenance_reserve": {
      "name": "Illustrative annual maintenance reserve",
      "description": "Owner-stock value proxy multiplied by the assumed reserve fraction.",
      "unitText": "USD per year"
    },
    "annual_management": {
      "name": "Illustrative annual management cost",
      "description": "Adjusted annual receipts multiplied by the assumed management fraction.",
      "unitText": "USD per year"
    },
    "annual_mortgage_insurance": {
      "name": "Assumed annual mortgage insurance",
      "description": "Explicit annual scenario cost; not an observed quote.",
      "unitText": "USD per year"
    },
    "annual_other_costs": {
      "name": "Assumed other annual costs",
      "description": "Explicit additional annual scenario cost.",
      "unitText": "USD per year"
    },
    "annual_principal_interest": {
      "name": "Illustrative annual principal and interest",
      "description": "Twelve fixed loan payments; insurance, taxes and other costs are separate.",
      "unitText": "USD per year"
    },
    "annual_property_tax": {
      "name": "Illustrative annual property tax",
      "description": "Owner-stock value proxy multiplied by the assumed annual property-tax fraction.",
      "unitText": "USD per year"
    },
    "annual_receipts": {
      "name": "Illustrative annual rental receipts",
      "description": "HUD monthly gross rent minus the assumed monthly utility deduction, multiplied by assumed paid months.",
      "unitText": "USD per year"
    },
    "break_even_gross_monthly_rent": {
      "name": "Illustrative break-even monthly gross rent",
      "description": "Utility deduction plus (fixed budget + principal/interest) / (paid months * (1 - management fraction)); unavailable when paid months are zero.",
      "unitText": "USD per month"
    },
    "break_even_gross_monthly_usd": {
      "name": "Illustrative break-even monthly gross rent",
      "description": "Same threshold as the area-level output; threshold depends on the owner proxy and assumptions, not a selected HUD area rent.",
      "unitText": "USD per month"
    },
    "cash_surplus_min_usd": {
      "name": "Lowest illustrative annual cash surplus",
      "description": "Minimum across retained HUD areas at the central ACS owner-value estimate and fixed scenario assumptions.",
      "unitText": "USD per year"
    },
    "cash_surplus_max_usd": {
      "name": "Highest illustrative annual cash surplus",
      "description": "Maximum across retained HUD areas at the central ACS owner-value estimate and fixed scenario assumptions.",
      "unitText": "USD per year"
    },
    "cbsa": {
      "name": "CBSA code",
      "description": "Five-character metropolitan-area identifier; preserve as text.",
      "unitText": "identifier"
    },
    "down_payment_fraction": {
      "name": "Assumed down-payment share",
      "description": "Scenario input expressed as a 0–1 fraction of the owner-value proxy.",
      "unitText": "fraction"
    },
    "geography_note": {
      "name": "Geographic comparison note",
      "description": "County-match/retained-exception note; distinct HUD subareas are not averaged.",
      "unitText": "label"
    },
    "hud_2br_gross_min_usd": {
      "name": "Lowest retained HUD two-bedroom gross rent",
      "description": "Minimum FY2027 two-bedroom FMR across candidate HUD areas in the metro.",
      "unitText": "USD per month"
    },
    "hud_2br_gross_max_usd": {
      "name": "Highest retained HUD two-bedroom gross rent",
      "description": "Maximum FY2027 two-bedroom FMR across candidate HUD areas in the metro.",
      "unitText": "USD per month"
    },
    "hud_2br_gross_monthly_usd": {
      "name": "HUD area two-bedroom gross rent",
      "description": "FY2027 two-bedroom FMR for this retained HUD area, including utility treatment; not landlord cash receipts.",
      "unitText": "USD per month"
    },
    "hud_area_code": {
      "name": "HUD rent-area code",
      "description": "Retained source HUD area identifier, distinct from a CBSA code.",
      "unitText": "identifier"
    },
    "hud_area_count": {
      "name": "Retained HUD area count",
      "description": "Number of distinct candidate HUD rent areas retained for this metropolitan area.",
      "unitText": "areas"
    },
    "hud_area_name": {
      "name": "HUD rent-area name",
      "description": "Published name of the retained HUD rent area.",
      "unitText": "label"
    },
    "hud_fiscal_year": {
      "name": "HUD benchmark fiscal year",
      "description": "Fiscal-year label of the FMR benchmark; not a calendar-year observation date.",
      "unitText": "fiscal year"
    },
    "input_status": {
      "name": "Scenario input status",
      "description": "Illustrative status label; not evidence of a performed investment or company test.",
      "unitText": "label"
    },
    "insurance_fraction": {
      "name": "Assumed annual insurance share",
      "description": "Annual property insurance as a 0–1 fraction of the owner-value proxy.",
      "unitText": "fraction"
    },
    "interpretation": {
      "name": "Interpretation limit",
      "description": "Explicit reminder that results are hypothetical budgets, not matched-property or observed returns.",
      "unitText": "label"
    },
    "loan_years": {
      "name": "Assumed loan term",
      "description": "Loan term used by the fixed-payment model.",
      "unitText": "years"
    },
    "maintenance_reserve_fraction": {
      "name": "Assumed annual maintenance share",
      "description": "Annual maintenance reserve as a 0–1 fraction of the owner-value proxy.",
      "unitText": "fraction"
    },
    "management_fraction": {
      "name": "Assumed management share",
      "description": "Management expense as a 0–1 fraction of adjusted receipts.",
      "unitText": "fraction"
    },
    "metro": {
      "name": "Metropolitan-area label",
      "description": "Published whole metropolitan-area name; not a property identifier.",
      "unitText": "label"
    },
    "monthly_hoa": {
      "name": "Assumed monthly HOA cost",
      "description": "Monthly scenario cost included twelve times in the annual fixed budget.",
      "unitText": "USD per month"
    },
    "monthly_utilities": {
      "name": "Assumed monthly utility deduction",
      "description": "Deduction from HUD gross rent before multiplying by paid months; not a measured utility bill.",
      "unitText": "USD per month"
    },
    "occupied_months": {
      "name": "Assumed paid months",
      "description": "Assumed paid months in the modeled year, between zero and twelve.",
      "unitText": "months per year"
    },
    "owner_value_moe_usd": {
      "name": "Published ACS owner-value margin of error",
      "description": "Source B25077 margin of error for the all-owner-stock median value; retained separately from derived scenario sensitivity.",
      "unitText": "USD"
    },
    "owner_value_proxy_usd": {
      "name": "ACS median owner-stock value proxy",
      "description": "ACS2024 B25077 all-owner-occupied-unit median value; not a price quote for a matching two-bedroom rental.",
      "unitText": "USD"
    },
    "price_endpoint_surplus_min_usd": {
      "name": "Lowest owner-value endpoint sensitivity",
      "description": "Minimum annual cash surplus across retained HUD areas and owner-value estimate ± published MOE; not a joint confidence interval.",
      "unitText": "USD per year"
    },
    "price_endpoint_surplus_max_usd": {
      "name": "Highest owner-value endpoint sensitivity",
      "description": "Maximum annual cash surplus across retained HUD areas and owner-value estimate ± published MOE; not a joint confidence interval.",
      "unitText": "USD per year"
    },
    "property_tax_fraction": {
      "name": "Assumed annual property-tax share",
      "description": "Annual property-tax cost as a 0–1 fraction of the owner-value proxy.",
      "unitText": "fraction"
    },
    "scenario": {
      "name": "Scenario identifier",
      "description": "Named set of fixed illustrative assumptions, repeated across metros/areas.",
      "unitText": "identifier"
    },
    "scenario_coverage": {
      "name": "Candidate-rent coverage category",
      "description": "Whether all, some or no retained HUD rents cover the modeled cash budget; not a property or investment rank.",
      "unitText": "label"
    }
  },
  "rent-burden": {
    "geo_id": {
      "name": "geo_id",
      "description": "Exact GEO_ID from the source geography file; keep as text, including its geography-vintage marker.",
      "unitText": "identifier"
    },
    "cbsa_code": {
      "name": "cbsa_code",
      "description": "Five-character CBSA code from the source geography file; preserve text and leading zeros.",
      "unitText": "identifier"
    },
    "metro_name": {
      "name": "metro_name",
      "description": "Published whole metropolitan-area label, not a property or city-only boundary.",
      "unitText": "label"
    },
    "survey_year": {
      "name": "survey_year",
      "description": "ACS 1-year source year, not download year or current market year.",
      "unitText": "year"
    },
    "status": {
      "name": "status",
      "description": "Analysis availability status. This fixed released snapshot contains only ok. The builder can also report unavailable source estimate or zero computable denominator.",
      "unitText": "status"
    },
    "renter_units_total": {
      "name": "renter_units_total",
      "description": "Total renter-occupied housing units; not a count of people or only cash-rent units.",
      "unitText": "housing units",
      "measurementTechnique": "B25070_E001"
    },
    "not_computed_units": {
      "name": "not_computed_units",
      "description": "Units for which the source ratio is not computed; retained separately, not treated as zero burden.",
      "unitText": "housing units",
      "measurementTechnique": "B25070_E011"
    },
    "computable_units": {
      "name": "computable_units",
      "description": "Denominator for the two threshold percentages.",
      "unitText": "housing units",
      "measurementTechnique": "B25070_E001 - B25070_E011"
    },
    "rent_30plus_units": {
      "name": "rent_30plus_units",
      "description": "Units in the published 30.0%-or-more bins.",
      "unitText": "housing units",
      "measurementTechnique": "B25070_E007 + B25070_E008 + B25070_E009 + B25070_E010"
    },
    "rent_50plus_units": {
      "name": "rent_50plus_units",
      "description": "Units in the published 50.0%-or-more bin; a subset of rent_30plus_units.",
      "unitText": "housing units",
      "measurementTechnique": "B25070_E010"
    },
    "rent_30plus_pct": {
      "name": "rent_30plus_pct",
      "description": "Share of computable units at 30.0% or more, rounded to six decimals; not a 0–1 fraction.",
      "unitText": "percent (0–100)",
      "measurementTechnique": "100 * rent_30plus_units / computable_units"
    },
    "rent_50plus_pct": {
      "name": "rent_50plus_pct",
      "description": "Share of computable units at 50.0% or more; nested inside the 30% group. Do not add these percentages.",
      "unitText": "percent (0–100)",
      "measurementTechnique": "100 * rent_50plus_units / computable_units"
    },
    "not_computed_pct_all_renters": {
      "name": "not_computed_pct_all_renters",
      "description": "Share of all renter-occupied units with a not-computed ratio; its denominator differs from the two burden percentages.",
      "unitText": "percent (0–100)",
      "measurementTechnique": "100 * not_computed_units / renter_units_total"
    },
    "B25070_E001": {
      "name": "B25070_E001",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M001": {
      "name": "B25070_M001",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E002": {
      "name": "B25070_E002",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M002": {
      "name": "B25070_M002",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E003": {
      "name": "B25070_E003",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M003": {
      "name": "B25070_M003",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E004": {
      "name": "B25070_E004",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M004": {
      "name": "B25070_M004",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E005": {
      "name": "B25070_E005",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M005": {
      "name": "B25070_M005",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E006": {
      "name": "B25070_E006",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M006": {
      "name": "B25070_M006",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E007": {
      "name": "B25070_E007",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M007": {
      "name": "B25070_M007",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E008": {
      "name": "B25070_E008",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M008": {
      "name": "B25070_M008",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E009": {
      "name": "B25070_E009",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M009": {
      "name": "B25070_M009",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E010": {
      "name": "B25070_E010",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M010": {
      "name": "B25070_M010",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_E011": {
      "name": "B25070_E011",
      "description": "Published estimate. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    },
    "B25070_M011": {
      "name": "B25070_M011",
      "description": "Published margin of error for the matching estimate; not the error of a derived percentage. Source token retained; a sentinel is not a valid count and never becomes zero.",
      "unitText": "housing units"
    }
  }
}''')



def enrich(relative, text):
    blocks = list(re.finditer(r'(<script type="application/ld\+json">)(.*?)(</script>)', text, re.S))
    if len(blocks) != 1:
        raise ValueError('Expected exactly one study JSON-LD graph')
    match = blocks[0]
    graph = json.loads(match[2])
    nodes = [node for node in graph['@graph'] if node.get('@type') == 'Dataset']
    if len(nodes) != 1:
        raise ValueError('Expected one Dataset')
    node = nodes[0]
    release, reuse = STUDIES[relative]
    node.update(sameAs=release, identifier=release, usageInfo=reuse,
                publisher={'@id': 'https://a-samadi.com/#person'})
    node['creator']['@id'] = 'https://a-samadi.com/#person'
    if relative == 'studies/rent-own-2026/index.html':
        node['spatialCoverage'] = ('393 metropolitan areas in the available ACS2024 one-year universe,including Puerto Rico;'
                                   'distinct HUD rent areas retained. Owner-stock and rental populations differ.')

    study = relative.split('/')[1]
    base = 'https://a-samadi.com/studies/' + study + '/'
    paths = ['metro-scenarios.csv', 'hud-area-scenarios.csv'] if study == 'rent-own-2026' else ['metro-rent-burden-2024.csv']
    columns = []
    for filename in paths:
        with (ROOT / 'studies' / study / filename).open(newline='') as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames
            rows = list(reader)
        assert len(header) == len(set(header))
        columns.extend(k for k in header if k not in columns)
        for distribution in node['distribution']:
            if distribution['contentUrl'] == base + filename:
                distribution['description'] = f'{len(rows)} rows; {len(header)} columns. See the column dictionary and scoped reuse terms on the study page.'
    assert set(columns) == set(FIELD_DEFINITIONS[study]), 'CSV fields changed; reconcile definitions first'
    node['variableMeasured'] = [dict({'@type': 'PropertyValue', 'propertyID': k}, **FIELD_DEFINITIONS[study][k]) for k in columns]
    node['license'] = {'@type': 'CreativeWork', 'name': 'CC BY 4.0 — original study contributions only',
                       'url': 'https://creativecommons.org/licenses/by/4.0/',
                       'text': 'To the extent copyright or similar rights exist and are held by Ahmadreza Samadi, original study explanations and analytical selection/arrangement are offered under CC BY 4.0. Underlying government data and documents retain their source status and exceptions. This grant does not cover code, third-party materials, fonts, portraits or marks; existing grants are not withdrawn.'}
    node['copyrightNotice'] = node['license']['text']
    node['usageInfo'] = [reuse, base + '#study-reuse']
    period = ['2024-01-01/2024-12-31', '2026-10-01/2027-09-30'] if study == 'rent-own-2026' else '2024-01-01/2024-12-31'
    node['temporalCoverage'] = period
    source_table = 'B25077' if study == 'rent-own-2026' else 'B25070'
    node['isBasedOn'] = [{'@type': 'Dataset', 'name': 'ACS 2024 one-year table ' + source_table,
        'url': 'https://data.census.gov/table/ACSDT1Y2024.' + source_table,
        'temporalCoverage': '2024-01-01/2024-12-31', 'creator': {'@type': 'Organization', 'name': 'U.S. Census Bureau'}}]
    if study == 'rent-own-2026':
        node['isBasedOn'].append({'@type': 'Dataset', 'name': 'HUD FY2027 Fair Market Rent benchmarks',
            'url': 'https://www.huduser.gov/portal/datasets/fmr.html', 'temporalCoverage': '2026-10-01/2027-09-30',
            'description': 'Benchmark applicability period, not a calendar-year observation or guarantee that every area rate is effective; reevaluation exceptions may apply.',
            'creator': {'@type': 'Organization', 'name': 'U.S. Department of Housing and Urban Development'}})
    title = 'Where does rent cover the cost of owning? 2026 metro edition' if study == 'rent-own-2026' else 'Metro rent burden: reproducible ACS 2024 point estimates'
    version = '1.0.0' if study == 'rent-own-2026' else '1.1.1'
    date = '2026-10-15' if study == 'rent-own-2026' else '2026-10-17'
    citation = f'Ahmadreza Samadi ({date}). {title}. Software/method version {version}. {base}'
    node['citation'] = [{'@type': 'SoftwareSourceCode', 'name': title, 'version': version,
        'datePublished': date, 'author': {'@id': 'https://a-samadi.com/#person'}, 'url': release},
        {'@type': 'Dataset', 'name': 'U.S. Census Bureau ACS 2024 one-year table ' + source_table,
         'url': 'https://data.census.gov/table/ACSDT1Y2024.' + source_table}]
    if study == 'rent-own-2026':
        node['citation'].append({'@type': 'Dataset', 'name': 'HUD FY2027 FMR', 'url': 'https://www.huduser.gov/portal/datasets/fmr.html'})
    dictionary = '<details><summary>CSV column dictionary (' + str(len(columns)) + ' distinct fields)</summary><dl>'
    for key in columns:
        f = FIELD_DEFINITIONS[study][key]
        dictionary += '<dt><code style="overflow-wrap:anywhere">' + escape(key) + '</code></dt><dd>' + escape(f['description']) + ' Unit: ' + escape(f['unitText']) + '.</dd>'
    dictionary += '</dl></details>'
    periods = ('ACS describes calendar year 2024. HUD inputs are FY2027 two-bedroom FMR benchmarks for the fiscal period 1 October 2026–30 September 2027; area-specific effective rates and reevaluation exceptions can differ. This mixed-vintage scenario is not an observed 2024–2027 time series. July 2023 geography defines boundaries, not a housing observation date.'
               if study == 'rent-own-2026' else 'The observations are ACS 2024 one-year estimates. They are not 2026 asking rents. Source estimate/MOE pairs are retained; derived percentage MOEs have not been calculated.')
    rights = ('Original study explanations and analytical selection/arrangement are shared under <a rel="license" href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>, to the extent Ahmadreza Samadi holds copyright or similar rights. Credit the author, link the licence and indicate changes. Underlying government data and documents retain their source status and exceptions; this does not relicense them or restrict public-domain facts. Existing code/dictionary licences, font notices, portraits and marks retain their own terms. Earlier grants are not withdrawn.')
    policies = '<a href="https://www2.census.gov/foia/ds_policies/ds027.pdf">Census DS027, page 9</a>'
    if study == 'rent-own-2026':
        policies += ' and <a href="https://www.hud.gov/sites/documents/webpubstandards.pdf">HUD web publication policy, section 1D</a>'
    section = ('\n<!-- study-publication-details:start -->\n<section class="panel" aria-labelledby="study-publication-details"><h2 id="study-publication-details">Dates, columns and reuse</h2>'
        '<p>' + escape(periods) + '</p>' + dictionary + '<h3 id="study-reuse">Reuse and citation</h3><p>' + rights + '</p>'
        '<p>Source notices: ' + policies + '. These sources do not endorse this analysis.</p><p>Suggested citation: ' + escape(citation) + '</p></section>\n<!-- study-publication-details:end -->\n')
    marker = re.compile(r'\n<!-- study-publication-details:start -->.*?<!-- study-publication-details:end -->\n', re.S)
    text = marker.sub('', text)
    # Graph offsets were calculated before removing the old visible block; it lies later in the document.

    replacement = json.dumps(graph, ensure_ascii=False, indent=2)
    result = text[:match.start(2)] + replacement + text[match.end(2):]
    if relative == 'studies/rent-burden/index.html':
        bio = json.loads((ROOT / 'locales/author-bios.json').read_text())['en']
        author = escape(bio).replace('Ahmadreza Samadi', '<a href="/about.html" rel="author">Ahmadreza Samadi</a>', 1)
        author_pattern = re.compile(r'(<h2 id="author">About the author</h2>)<p>.*?</p>(?:<p class="small" data-brand-series>.*?</p>)?', re.S)
        result, count = author_pattern.subn(lambda match: match[1] + '<p>' + author + '</p><p class="small" data-brand-series>Part of Property Decision Data</p>', result)
        if count != 1:
            raise ValueError('Expected one existing study author paragraph')
        footer_links = '<a href="/ideas.html">Signature ideas</a> · <a href="/studies/">Property Decision Data</a> · '
        if footer_links not in result:
            if result.count('<footer>') != 1:
                raise ValueError('Expected one study footer')
            result = result.replace('<footer>', '<footer>' + footer_links, 1)
    if relative == 'studies/rent-burden/index.html':
        anchor = '<section class="panel" aria-labelledby="author">'
    else:
        anchor = '<p class="attribution">'
    if result.count(anchor) != 1:
        raise ValueError('Expected one study publication-details anchor')
    result = result.replace(anchor, section + anchor, 1)
    return result


if __name__ == '__main__':
    check = '--check' in sys.argv
    changed = []
    for relative in STUDIES:
        path = ROOT / relative
        original = path.read_text()
        updated = enrich(relative, original)
        if original == updated:
            continue
        changed.append(relative)
        if not check:
            if path.read_text() != original:
                raise RuntimeError('Concurrent study edit')
            path.write_text(updated)
    print(('STALE ' if check and changed else 'PASS ') + 'study identities/reuse notes: ' + ', '.join(changed or ['no changes needed']))
    if check and changed:
        raise SystemExit(1)
