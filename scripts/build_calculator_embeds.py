"""Keep attributed, unmeasured calculator embeds aligned with their primary pages."""
from pathlib import Path
import re,sys
ROOT=Path(__file__).resolve().parent.parent
def embedded(source,stem):
    if 'data-share' not in source or 'data-print-inputs' not in source:raise ValueError('Primary calculator lacks sharing controls')
    result=source.replace('class="property-calculator"','class="property-calculator calculator-embed"')
    result=re.sub(r'(<title>)(.*?)(</title>)',lambda m:m[1]+m[2]+' (embed)'+m[3],result,count=1)
    if 'calculator-embed' not in result:result=re.sub(r'<body\b([^>]*class=")',r'<body\1calculator-embed ',result,count=1)
    result=re.sub(r'<meta name="robots" content="[^"]*">','<meta name="robots" content="noindex,follow">',result)
    result=re.sub(r'<script src="/js/site-analytics.js[^\"]*" defer></script>','',result)
    result=result.replace('</main>',f'<p class="embed-attribution">Calculator by <a href="/about.html">Ahmadreza Samadi</a> · <a href="/tools/{stem}.html">Full calculator and sources</a>. Your inputs are not independently verified facts or quotes.</p></main>',1)
    if 'site-analytics.js' in result or 'data-cf-beacon' in result:raise ValueError('Embed must not contain analytics')
    return result
def main():
    check='--check' in sys.argv;changed=[]
    for stem in ['rental-cash-flow','dubai-purchase-cost','valuation-range']:
        primary=ROOT/'tools'/f'{stem}.html';destination=ROOT/'tools/embed'/f'{stem}.html';result=embedded(primary.read_text(),stem)
        old=destination.read_text() if destination.exists() else None
        if old!=result:
            changed.append(stem)
            if not check:
                if destination.exists() and destination.read_text()!=old:raise RuntimeError('Concurrent embed edit')
                destination.parent.mkdir(exist_ok=True);destination.write_text(result)
    if check and changed:raise SystemExit('STALE calculator embeds: '+', '.join(changed))
    print('PASS calculator embeds:3; '+str(len(changed))+' changes')
if __name__=='__main__':main()
