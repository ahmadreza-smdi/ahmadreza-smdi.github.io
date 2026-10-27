function number(value){if(value===null||value===undefined||String(value).trim()==='')return null;const n=Number(value);return Number.isFinite(n)?n:null;}
function display(value,kind='number'){const n=number(value);if(n===null)return 'Unavailable';return new Intl.NumberFormat('en-US',{maximumFractionDigits:kind==='percent'?1:0,minimumFractionDigits:kind==='percent'?1:0}).format(n)+(kind==='percent'?'%':'');}
function normalizedSearch(value) {
  return String(value).normalize('NFKC').toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}

function selectRows(data, dataset, query, scenario) {
  if (!['burden', 'ownership'].includes(dataset)) throw new Error('Unknown dataset');
  const raw = query.trim();
  const q = normalizedSearch(raw);
  return data[dataset].filter(r =>
    (dataset !== 'ownership' || r.scenario === scenario) &&
    (!raw || (q && [r.metro_name || r.metro, r.cbsa_code || r.cbsa]
      .some(value => normalizedSearch(value).includes(q)))))
    .sort((a, b) => (a.metro_name || a.metro).localeCompare(b.metro_name || b.metro));
}

function pageRows(rows,page,size=25){const total=Math.max(1,Math.ceil(rows.length/size));const current=Math.max(0,Math.min(page,total-1));return {rows:rows.slice(current*size,(current+1)*size),page:current,pages:total,total:rows.length};}

const $=id=>document.getElementById(id);let page=0;
function render(){const kind=$('dataset').value;const own=kind==='ownership';$('scenario-wrap').hidden=!own;$('assumptions').hidden=!own;if(own){const r=DATA.ownership.find(r=>r.scenario===$('scenario').value);const pct=k=>display(100*number(r[k]),'percent');$('assumption-values').textContent=`Down payment ${pct('down_payment_fraction')}; fixed annual interest ${pct('annual_interest_rate')}; term ${r.loan_years} years (unused in the all-cash case); paid months ${r.occupied_months}/year; management ${pct('management_fraction')} of receipts; annual tax ${pct('property_tax_fraction')}, insurance ${pct('insurance_fraction')} and maintenance reserve ${pct('maintenance_reserve_fraction')} of the value proxy; monthly utilities deducted from gross rent USD ${display(r.monthly_utilities)}; monthly HOA USD ${display(r.monthly_hoa)}; other annual costs USD ${display(r.annual_other_costs)}; annual mortgage insurance USD ${display(r.annual_mortgage_insurance)}.`;}const rows=selectRows(DATA,kind,$('search').value,$('scenario').value);const result=pageRows(rows,page);page=result.page;
$('scope').textContent=own?'393 metros · HUD FY2027 two-bedroom gross rent + ACS 2024 owner-stock value · hypothetical budgets':'386 metros · ACS 2024 B25070 · renter-occupied housing units in 50 states/DC';
$('limits').textContent=own?'These are illustrative scenarios, not observed returns, current asking rents or a matched-property yield. HUD subareas remain a range, not an average. Select a scenario; the complete CSV includes its assumptions and price-proxy uncertainty endpoints.':'30%+ and 50%+ use computable units only; the 50%+ group is inside 30%+. Not-computed units are shown separately. Their percentage uses all renter-occupied units, including those excluded from the computable denominator. These are survey point estimates: derived percentage margins of error are not calculated, and differences are not established as statistically significant.';
$('method').href=own?'https://a-samadi.com/studies/rent-own-2026/':'https://github.com/ahmadreza-smdi/metro-rent-burden/releases/tag/v1.0.0';
const download=DOWNLOADS.find(d=>d.dataset===kind);$('csv').href=download.url;$('csv').download=download.filename;
const headers=own?['Metro / CBSA','Owner-stock value proxy (USD)','HUD gross rent/month range (USD)','Hypothetical annual surplus range (USD)']:['Metro / CBSA','Computable units','Not-computed units','Not computed (% of all renter units)','30%+ of income','50%+ of income'];
$('head').replaceChildren(...headers.map(t=>{const th=document.createElement('th');th.scope='col';th.textContent=t;return th;}));
$('body').replaceChildren(...result.rows.map(r=>{const tr=document.createElement('tr');const vals=own?[`${r.metro} / ${r.cbsa}`,display(r.owner_value_proxy_usd),`${display(r.hud_2br_gross_min_usd)} to ${display(r.hud_2br_gross_max_usd)}`,`${display(r.cash_surplus_min_usd)} to ${display(r.cash_surplus_max_usd)}`]:[`${r.metro_name} / ${r.cbsa_code}`,display(r.computable_units),display(r.not_computed_units),display(r.not_computed_pct_all_renters,'percent'),display(r.rent_30plus_pct,'percent'),display(r.rent_50plus_pct,'percent')];tr.append(...vals.map((v,i)=>{const td=document.createElement(i===0?'th':'td');if(i===0)td.scope='row';td.textContent=v;return td;}));return tr;}));
$('results').textContent=rows.length?`${rows.length} matching ${rows.length===1?'metro':'metros'}. Page ${page+1} of ${result.pages}. Alphabetical order.`:'No matching metros. Try a metro name, state abbreviation or CBSA code.';$('prev').disabled=page===0;$('next').disabled=page+1>=result.pages;
}
for(const id of ['dataset','scenario'])$(id).addEventListener('change',()=>{page=0;render();});$('search').addEventListener('input',()=>{page=0;render();});$('prev').onclick=()=>{page--;render();};$('next').onclick=()=>{page++;render();};render();

function matchingCSV(rows, columns) {
  const cell = value => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  return [columns, ...rows.map(row => columns.map(key => row[key]))]
    .map(row => row.map(cell).join(',')).join('\r\n') + '\r\n';
}

function updateMatchingDownload() {
  const kind = $('dataset').value;
  const rows = selectRows(DATA, kind, $('search').value, $('scenario').value);
  const link = $('matching-csv');
  link.textContent = `Download ${rows.length} matching ${rows.length === 1 ? 'row' : 'rows'} (CSV)`;
  if (!rows.length) {
    link.removeAttribute('href');
    link.removeAttribute('download');
    link.setAttribute('aria-disabled', 'true');
    return;
  }
  const csv = matchingCSV(rows, Object.keys(DATA[kind][0]));
  link.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
  link.download = kind === 'ownership'
    ? `ownership-${$('scenario').value}-matching.csv`
    : 'rent-burden-matching.csv';
  link.removeAttribute('aria-disabled');
}

if (typeof document !== 'undefined') {
  for (const id of ['dataset', 'scenario']) $(id).addEventListener('change', updateMatchingDownload);
  $('search').addEventListener('input', updateMatchingDownload);
  updateMatchingDownload();
}

const DEFAULT_SCENARIO = 'illustrative-financed';
const SCENARIOS = ['illustrative-financed', 'illustrative-cash', 'illustrative-stress'];

function encodeView(state) {
  const params = new URLSearchParams();
  params.set('view', '1');
  params.set('dataset', state.dataset === 'ownership' ? 'ownership' : 'burden');
  params.set('scenario', SCENARIOS.includes(state.scenario) ? state.scenario : DEFAULT_SCENARIO);
  if (state.query) params.set('q', state.query);
  if (Number.isSafeInteger(state.page) && state.page > 0) params.set('page', String(state.page + 1));
  return '#' + params.toString();
}

function decodeView(hash) {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  if (params.get('view') !== '1') return null;
  const rawPage = params.get('page') || '1';
  const requested = /^[1-9][0-9]*$/.test(rawPage) ? Number(rawPage) : 1;
  return {
    dataset: params.get('dataset') === 'ownership' ? 'ownership' : 'burden',
    scenario: SCENARIOS.includes(params.get('scenario')) ? params.get('scenario') : DEFAULT_SCENARIO,
    query: params.get('q') || '',
    page: Number.isSafeInteger(requested) ? requested - 1 : 0,
  };
}

if (typeof document !== 'undefined') {
  const priorRender = render;
  render = function () {
    priorRender();
    $('saved-view-status').textContent = 'Save the current selection to update the address bar. The link includes your search text.';
  };
  function restoreView() {
    const state = decodeView(location.hash);
    if (!state) return;
    $('dataset').value = state.dataset;
    $('scenario').value = state.scenario;
    $('search').value = state.query;
    page = state.page;
    render();
    updateMatchingDownload();
    $('saved-view-status').textContent = 'Saved selection opened. Values come from the data currently supplied with this explorer.';
  }
  $('save-view').addEventListener('click', () => {
    const fragment = encodeView({dataset: $('dataset').value, scenario: $('scenario').value, query: $('search').value, page});
    history.replaceState(null, '', location.pathname + location.search + fragment);
    $('saved-view-status').textContent = 'Current selection saved in the address bar. Copy or bookmark this URL. It includes your search text, not a frozen data snapshot.';
  });
  window.addEventListener('hashchange', restoreView);
  restoreView();
}

const SELECTION_SOURCES=[{"dataset":"burden","filename":"metro-rent-burden-2024.csv","sha256":"3f4f802c00efda62f2166cf0f6cfef99d0046becda55ba35c9563c232d84821f"},{"dataset":"ownership","filename":"metro-scenarios.csv","sha256":"1c5c2e685fbb56796854bf027c3042105ac03be676428b16e80731942e5f6d00"}];
const SELECTION_SCENARIOS = {
  'illustrative-financed': 'Financed',
  'illustrative-cash': 'Cash',
  'illustrative-stress': 'Stress',
};

function selectionNotes(view, sources) {
  if (!['burden', 'ownership'].includes(view.dataset)) throw new Error('Unknown study');
  const source = sources.find(item => item.dataset === view.dataset);
  if (!source || !/^[a-f0-9]{64}$/.test(source.sha256) ||
      typeof source.filename !== 'string' || /[\r\n]/.test(source.filename)) {
    throw new Error('Original CSV reference unavailable');
  }
  for (const key of ['matchingRows', 'visibleRows', 'page', 'pages']) {
    if (!Number.isSafeInteger(view[key]) || view[key] < 0) throw new Error('Invalid result count');
  }
  if (view.pages < 1 || view.page >= view.pages || view.visibleRows > view.matchingRows ||
      view.visibleRows > 25 || typeof view.query !== 'string') throw new Error('Invalid view');
  const ownership = view.dataset === 'ownership';
  if (ownership && !Object.hasOwn(SELECTION_SCENARIOS, view.scenario)) throw new Error('Unknown scenario');
  const lines = [
    'Property studies explorer: selection notes',
    'Analysis by Ahmadreza Samadi',
    'https://a-samadi.com/about.html',
    '',
    ownership ? 'Study: Illustrative ownership budgets' : 'Study: Rent burden',
    ownership ? 'Data: HUD FY2027 two-bedroom gross rent + ACS 2024 owner-stock value.'
      : 'Data: ACS 2024 B25070; renter-occupied housing units in 50 states/DC.',
    'Search text: ' + JSON.stringify(view.query).replace(/[\u0085\u2028\u2029]/g, c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0')),
    ownership ? 'Hypothetical scenario: ' + SELECTION_SCENARIOS[view.scenario] : 'Scenario: not applicable to this study.',
    'Matching rows across all result pages: ' + view.matchingRows,
    'Visible rows: ' + view.visibleRows,
    'Visible page: ' + (view.page + 1) + ' of ' + view.pages,
    '',
    'Original CSV: ' + source.filename,
    'Original CSV SHA-256: ' + source.sha256,
    'Method and limitations: ' + (ownership
      ? 'https://a-samadi.com/studies/rent-own-2026/'
      : 'https://github.com/ahmadreza-smdi/metro-rent-burden/releases/tag/v1.0.0'),
    '',
    'These notes describe the selection, not a frozen numeric snapshot or a record of a completed download.',
    'Download the matching-row CSV separately. It contains all matching rows across pages, not only the visible page.',
    'That CSV is newly generated; the hash above identifies the complete original CSV, not the matching-row export or this TXT.',
    ownership
      ? 'Budgets are hypothetical, not observed returns or matched-property yields. Read the selected assumptions and exclusions in the explorer and study.'
      : 'The 50%+ group is inside 30%+. Not-computed units are separate; missing values are not zero. Differences are not established as statistically significant.',
    'The studies differ in geography, periods and measures; these notes do not join or rank them.',
    'Educational, not financial advice.',
  ];
  return lines.join('\n') + '\n';
}

if (typeof document !== 'undefined') {
  function updateSelectionNotes() {
    const link = $('selection-notes');
    try {
      const rows = selectRows(DATA, $('dataset').value, $('search').value, $('scenario').value);
      const result = pageRows(rows, page);
      const notes = selectionNotes({dataset: $('dataset').value, query: $('search').value,
        scenario: $('scenario').value, matchingRows: rows.length, visibleRows: result.rows.length,
        page: result.page, pages: result.pages}, SELECTION_SOURCES);
      link.href = 'data:text/plain;charset=utf-8,' + encodeURIComponent(notes);
      link.download = $('dataset').value + '-selection-notes.txt';
      link.textContent = 'Download selection notes (TXT)';
      link.removeAttribute('aria-disabled');
      return true;
    } catch {
      link.removeAttribute('href');
      link.removeAttribute('download');
      link.setAttribute('aria-disabled', 'true');
      link.textContent = 'Selection notes unavailable';
      return false;
    }
  }
  const renderBeforeNotes = render;
  render = function () { renderBeforeNotes(); updateSelectionNotes(); };
  $('selection-notes').addEventListener('click', event => {
    if (!updateSelectionNotes()) event.preventDefault();
  });
  updateSelectionNotes();
}
