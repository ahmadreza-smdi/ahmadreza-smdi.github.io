/* Intelligence engine for the homepage.
   Dubai clock, the Ask panel (it searches this page and streams back the best passage), the
   portrait frame that leans toward the pointer, and a few small agentic details.
   Everything here is an enhancement: without this file the page is complete and readable. */
(() => {
    'use strict';
    const root = document.documentElement;
    const lang = root.lang || 'en';
    const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const $ = (selector, scope = document) => scope.querySelector(selector);
    const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
    const paused = () => reduceQuery.matches || root.classList.contains('motion-paused');
    const asking = () => root.classList.contains('agent-active');
    const i18n = (key, fallback) => {
        const node = document.querySelector(`[data-i18n="${key}"]`);
        return node ? node.textContent.trim() : fallback;
    };
    const motionListeners = [];
    const onMotion = (listener) => motionListeners.push(listener);
    window.addEventListener('site:motion', (event) => motionListeners.forEach((listener) => listener(event.detail || {})));
    window.addEventListener('site:ask', () => motionListeners.forEach((listener) => listener({})));

    /* Local time in Dubai, refreshed on the minute. */
    function clock() {
        const time = $('[data-clock]');
        if (!time) return;
        const locale = lang === 'fa' ? 'fa-IR' : lang === 'ar' ? 'ar-AE' : 'en-GB';
        let format;
        try {
            format = new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Dubai' });
        } catch (error) { return; }
        const tick = () => {
            const now = new Date();
            time.textContent = format.format(now);
            time.dateTime = now.toISOString();
            window.setTimeout(tick, 60000 - (now.getSeconds() * 1000 + now.getMilliseconds()) + 40);
        };
        tick();
    }

    /* The Ask panel: any Ask button, ⌘K, Ctrl K or "/" opens it. It filters the shortcuts, searches the
       text of this page, streams back the best passage and can take you to it. Arrows move, Enter
       opens, Esc closes. */
    function askPanel() {
        const dialog = $('dialog.command');
        const triggers = $$('[data-ask]');
        if (!dialog || typeof dialog.showModal !== 'function') {
            triggers.forEach((trigger) => { trigger.hidden = true; });
            return;
        }
        const input = $('.command-input', dialog);
        const answer = $('.command-answer', dialog);
        const answerText = answer && $('.answer-text', answer);
        const answerSection = answer && $('.answer-section', answer);
        const answerGo = answer && $('[data-answer-go]', answer);
        const commands = $$('.command-item', dialog).filter((item) => !item.hasAttribute('data-answer-go'));
        const everything = answerGo ? [answerGo, ...commands] : commands;
        const groups = $$('.command-group', dialog);
        const empty = $('.command-empty', dialog);
        const apple = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || '');
        $$('[data-command-key]').forEach((key) => {
            if (finePointer.matches) key.textContent = apple ? '⌘K' : 'Ctrl K';
            else key.hidden = true;
        });
        // The full prompt names the field for assistive technology; narrow screens show the short form.
        const fullPrompt = i18n('search', 'Ask about my work or jump to a section');
        const shortPrompt = ($('.ask-label') || {}).textContent || fullPrompt;
        const fitPrompt = () => { input.placeholder = input.offsetWidth && input.offsetWidth < 340 ? shortPrompt.trim() : fullPrompt; };
        if (input) {
            input.setAttribute('aria-label', fullPrompt);
            input.placeholder = fullPrompt;
            window.addEventListener('resize', fitPrompt, { passive: true });
        }

        // Latin accents and Arabic diacritics are ignored; Arabic and Persian letter variants match each other.
        const normalize = (value) => value.toLocaleLowerCase(lang).normalize('NFKD')
            .replace(/[\u0300-\u036f\u064b-\u065f\u0670]/g, '')
            .replace(/[\u064a\u0649]/g, '\u06cc').replace(/\u0643/g, '\u06a9').replace(/\u0629/g, '\u0647')
            .replace(/[\u200c\u200d\u0640]/g, ' ');
        const stop = new Set(['the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'and', 'or', 'is', 'are', 'was', 'what', 'who', 'how', 'where', 'when', 'why', 'which', 'does', 'do', 'did', 'he', 'his', 'him', 'me', 'my', 'you', 'your', 'with', 'about', 'tell', 'show', 'can', 'please']);
        const termsOf = (value) => {
            const all = normalize(value).split(/[\s.,;:!?()«»"“”'’\-–—/·|&]+/).filter((term) => term.length > 1);
            const useful = all.filter((term) => !stop.has(term));
            return useful.length ? useful : all;
        };
        const clean = (node) => node.textContent.replace(/\s+/g, ' ').trim();

        // The page index: each card, log entry, capability or paragraph is one place you can be taken to.
        let index = null;
        const build = () => {
            const places = $$('.hero-copy, .venture, .section-heading, .feature, .work-card, .bio-copy > p, .timeline-item, .capability, .guide-tile, .writing-item, .contact-copy', $('main'));
            index = places.map((place) => {
                const section = place.closest('section');
                const label = section && section.querySelector('.section-label');
                const title = place.matches('p') ? null : place.querySelector('h1, h2, h3, strong');
                const paragraphs = place.matches('p') ? [place] : $$('p', place).filter((p) => !p.matches('.section-label, .card-topline, .topic, .copy-status, .company') && clean(p).length > 24);
                return {
                    element: place,
                    weight: place.matches('.feature, .work-card, .timeline-item') ? 0.3 : 0,
                    section: label ? clean(label) : section && section.getAttribute('aria-label') || '',
                    title: title ? clean(title) : '',
                    titleNorm: title ? normalize(clean(title)) : '',
                    paragraphs: paragraphs.map((p) => ({ text: clean(p), norm: normalize(clean(p)) })),
                    norm: normalize(clean(place))
                };
            });
        };
        const search = (query) => {
            if (!index) build();
            const words = termsOf(query);
            if (!words.length) return null;
            let best = null;
            index.forEach((entry) => {
                let hits = 0;
                let score = 0;
                words.forEach((word) => {
                    const at = entry.norm.indexOf(word);
                    if (at < 0) return;
                    hits += 1;
                    score += 1 + Math.min(word.length, 10) / 10;
                    if (at === 0 || /\s/.test(entry.norm[at - 1])) score += 0.35;
                    if (entry.titleNorm.includes(word)) score += 0.6;
                });
                if (!hits) return;
                const coverage = hits / words.length;
                if (words.length > 1 && coverage < 0.5) return;
                score = score * coverage * coverage + entry.weight - Math.min(entry.norm.length, 1200) / 4000;
                if (!best || score > best.score) best = { entry, score, words };
            });
            return best;
        };

        let current = null;
        let answerTimer = 0;
        let streamTimer = 0;
        const showAnswer = (match) => {
            if (!answer) return;
            if (!match) {
                window.clearTimeout(streamTimer);
                current = null;
                answer.hidden = true;
                return;
            }
            const { entry, words } = match;
            const ranked = entry.paragraphs.map((p) => ({ p, hits: words.filter((word) => p.norm.includes(word)).length }));
            ranked.sort((a, b) => b.hits - a.hits);
            const source = ranked.length ? ranked[0].p.text : '';
            let excerpt = source || entry.title;
            if (excerpt.length > 230) {
                const lower = excerpt.toLocaleLowerCase(lang);
                const first = Math.max(0, ...words.map((word) => lower.indexOf(word)).filter((at) => at >= 0).slice(0, 1));
                const startAt = Math.max(0, excerpt.lastIndexOf(' ', Math.max(0, first - 80)));
                excerpt = (startAt > 0 ? '… ' : '') + excerpt.slice(startAt, startAt + 220).trim() + '…';
            }
            // Rebuild when the passage or the words being highlighted change.
            const key = `${excerpt}\u0000${words.join(' ')}`;
            if (current && current.entry === entry && current.key === key) {
                answer.hidden = false;
                return;
            }
            current = { entry, excerpt, key };
            answerSection.textContent = entry.section;
            answerText.replaceChildren();
            window.clearTimeout(streamTimer);
            const pieces = [];
            const addWords = (text, strong) => {
                text.split(/\s+/).filter(Boolean).forEach((word) => {
                    const hit = words.some((term) => normalize(word).includes(term));
                    const node = hit ? document.createElement('mark') : strong ? document.createElement('strong') : document.createTextNode(word);
                    if (hit || strong) node.textContent = word;
                    pieces.push(node);
                });
            };
            if (entry.title && source && !source.startsWith(entry.title)) addWords(entry.title + (/[.!?؟:]$/.test(entry.title) ? '' : ' —'), true);
            addWords(excerpt, false);
            answer.hidden = false;
            // The reply streams in a few words at a time, like an answer being written.
            const stream = () => {
                pieces.splice(0, paused() ? pieces.length : 3).forEach((node) => answerText.append(node, ' '));
                if (pieces.length) streamTimer = window.setTimeout(stream, 22);
            };
            stream();
        };
        const visible = () => everything.filter((item) => !item.hidden && !(item === answerGo && answer.hidden));
        const setActive = (active) => everything.forEach((item) => item.classList.toggle('is-active', item === active));
        const settleActive = () => {
            const shownCommands = commands.filter((item) => !item.hidden);
            setActive(shownCommands[0] || (answer && !answer.hidden ? answerGo : null));
        };
        const filter = () => {
            const raw = input.value.trim();
            const query = normalize(raw);
            let found = false;
            commands.forEach((item) => {
                if (item.dataset.unavailable === 'true') { item.hidden = true; return; }
                const haystack = normalize(`${item.textContent} ${item.getAttribute('href') || ''} ${item.dataset.icon || ''}`);
                item.hidden = Boolean(query) && !haystack.includes(query);
                found = found || !item.hidden;
            });
            groups.forEach((group) => {
                let next = group.nextElementSibling;
                let any = false;
                while (next && !next.classList.contains('command-group')) {
                    if (!next.hidden) any = true;
                    next = next.nextElementSibling;
                }
                group.hidden = !any;
            });
            window.clearTimeout(answerTimer);
            if (raw.length < 2) {
                showAnswer(null);
                empty.hidden = found;
                settleActive();
                return;
            }
            const match = search(raw);
            const hadAnswer = Boolean(current);
            // A previous passage must not remain clickable while the new query settles.
            showAnswer(null);
            empty.hidden = found || Boolean(match);
            answerTimer = window.setTimeout(() => { showAnswer(match); settleActive(); }, hadAnswer ? 160 : 60);
            settleActive();
        };
        let lastFocus = null;
        let keepFocus = false;
        const announce = (active) => {
            root.classList.toggle('agent-active', active);
            window.dispatchEvent(new CustomEvent('site:ask', { detail: { active } }));
        };
        const open = () => {
            if (dialog.open) return;
            lastFocus = document.activeElement;
            input.value = '';
            filter();
            dialog.showModal();
            fitPrompt();
            announce(true);
            input.focus();
        };
        const close = () => { if (dialog.open) dialog.close(); };
        dialog.addEventListener('close', () => {
            window.clearTimeout(answerTimer);
            window.clearTimeout(streamTimer);
            announce(false);
            if (!keepFocus && lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus({ preventScroll: true });
            keepFocus = false;
        });
        const closeButton = $('.command-close', dialog);
        if (closeButton) closeButton.addEventListener('click', close);
        triggers.forEach((trigger) => trigger.addEventListener('click', open));
        const typing = (target) => Boolean(target && target.closest && target.closest('input, textarea, select, [contenteditable="true"]'));
        document.addEventListener('keydown', (event) => {
            if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                if (dialog.open) close(); else open();
            } else if (event.key === '/' && !dialog.open && !typing(event.target) && !event.metaKey && !event.ctrlKey) {
                event.preventDefault();
                open();
            }
        });
        input.addEventListener('input', filter);
        input.addEventListener('keydown', (event) => {
            const list = visible();
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                if (list[0]) list[0].focus();
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                if (list.length) list[list.length - 1].focus();
            } else if (event.key === 'Enter') {
                if (input.value.trim().length >= 2 && answer && answer.hidden) {
                    window.clearTimeout(answerTimer);
                    showAnswer(search(input.value.trim()));
                    settleActive();
                }
                const active = visible().find((item) => item.classList.contains('is-active')) || visible()[0];
                if (active) {
                    event.preventDefault();
                    active.click();
                }
            }
        });
        dialog.addEventListener('keydown', (event) => {
            const item = event.target.closest && event.target.closest('.command-item');
            if (!item) return;
            const list = visible();
            const at = list.indexOf(item);
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                (list[at + 1] || input).focus();
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                (list[at - 1] || input).focus();
            } else if (event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey && event.key !== ' ') {
                input.focus();
            }
        });
        everything.forEach((item) => {
            item.addEventListener('focus', () => setActive(item));
            item.addEventListener('pointermove', () => { if (!item.classList.contains('is-active')) setActive(item); });
        });
        const reveal = (target, block) => {
            keepFocus = true;
            close();
            target.scrollIntoView({ behavior: paused() ? 'auto' : 'smooth', block });
            if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
            target.focus({ preventScroll: true });
        };
        dialog.addEventListener('click', (event) => {
            if (event.target === dialog) { close(); return; }
            const item = event.target.closest('.command-item');
            if (!item || item.hasAttribute('data-copy-email')) return;
            if (item.hasAttribute('data-answer-go')) {
                let target = current && current.entry.element;
                if (!target) return;
                // On one-column layouts the hero copy has no box of its own; take the reader to its section.
                if (getComputedStyle(target).display === 'contents') target = target.closest('section') || target.firstElementChild;
                reveal(target, 'center');
                target.classList.remove('is-found');
                void target.offsetWidth;
                target.classList.add('is-found');
                window.setTimeout(() => target.classList.remove('is-found'), 2800);
                return;
            }
            if (item.hasAttribute('data-motion-command')) {
                event.preventDefault();
                const toggle = $('.motion-toggle');
                if (toggle && !toggle.hidden) toggle.click();
                return;
            }
            const href = item.getAttribute('href') || '';
            if (href.startsWith('#')) {
                event.preventDefault();
                const target = document.getElementById(href.slice(1));
                if (!target) { close(); return; }
                history.pushState(null, '', href);
                reveal(target, 'start');
            } else {
                close();
            }
        });
    }

    /* Copy email with a visible, announced confirmation. */
    function copyEmail() {
        const buttons = $$('[data-copy-email]');
        if (!buttons.length) return;
        const link = $('.contact-email');
        const email = link ? link.textContent.trim() : 'ahmadreza.smdi@gmail.com';
        const status = $('.copy-status');
        const message = i18n('copied', 'Email address copied');
        let timer = 0;
        const write = async (isCurrent) => {
            try {
                await navigator.clipboard.writeText(email);
                return true;
            } catch (error) {
                if (!isCurrent()) return false;
                const area = document.createElement('textarea');
                area.value = email;
                area.setAttribute('readonly', '');
                area.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
                document.body.append(area);
                area.select();
                let copied = false;
                try { copied = document.execCommand('copy'); } catch (fallbackError) { copied = false; }
                area.remove();
                return copied;
            }
        };
        buttons.forEach((button) => {
            const dialog = button.classList.contains('command-item') ? button.closest('dialog') : null;
            const label = button.textContent;
            let feedbackTimer = 0;
            let operation = 0;
            const reset = () => {
                operation += 1;
                window.clearTimeout(feedbackTimer);
                feedbackTimer = 0;
                if (button.classList.contains('is-copied')) {
                    button.textContent = label;
                    button.classList.remove('is-copied');
                }
            };
            if (dialog) {
                dialog.addEventListener('close', () => { if (!dialog.open) reset(); });
                // A reopened Ask panel is a new session, even if the old close event is still queued.
                window.addEventListener('site:ask', (event) => { if (event.detail.active) reset(); });
            }
            button.addEventListener('click', async () => {
                if (button.classList.contains('is-copied')) return;
                const request = ++operation;
                const isCurrent = () => request === operation && (!dialog || dialog.open);
                const copied = await write(isCurrent);
                if (!isCurrent()) return;
                if (!copied) {
                    if (link) window.getSelection().selectAllChildren(link);
                    return;
                }
                if (status) {
                    status.textContent = message;
                    status.classList.remove('is-fresh');
                    void status.offsetWidth;
                    status.classList.add('is-fresh');
                    window.clearTimeout(timer);
                    timer = window.setTimeout(() => { status.textContent = ''; }, 4500);
                }
                if (dialog) {
                    button.textContent = message;
                    button.classList.add('is-copied');
                    feedbackTimer = window.setTimeout(() => {
                        if (!isCurrent()) return;
                        reset();
                        dialog.close();
                    }, 900);
                }
            });
        });
    }

    /* The marker that follows the hovered or current section link. */
    function navGlow() {
        const nav = $('.site-nav');
        const pill = nav && $('.nav-glow', nav);
        if (!pill) return;
        const links = $$('a', nav);
        let hovered = null;
        const place = () => {
            const target = hovered || links.find((link) => link.classList.contains('is-active'));
            if (!target || getComputedStyle(pill).display === 'none') {
                nav.style.setProperty('--nav-o', '0');
                return;
            }
            nav.style.setProperty('--nav-x', `${target.offsetLeft}px`);
            nav.style.setProperty('--nav-w', `${target.offsetWidth}px`);
            nav.style.setProperty('--nav-o', '1');
        };
        links.forEach((link) => {
            link.addEventListener('pointerenter', () => { hovered = link; place(); });
            link.addEventListener('focus', () => { hovered = link; place(); });
            link.addEventListener('blur', () => { hovered = null; place(); });
        });
        nav.addEventListener('pointerleave', () => { hovered = null; place(); });
        new MutationObserver(place).observe(nav, { subtree: true, attributes: true, attributeFilter: ['class'] });
        window.addEventListener('resize', place, { passive: true });
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(place);
        place();
    }

    /* A scan passes over the portrait once the page has opened, and again whenever the pointer
       arrives on it; the frame leans a little toward the pointer. */
    function lensTilt() {
        const hero = $('.hero');
        const lens = $('[data-lens]');
        if (!hero || !lens) return;
        const scan = () => {
            if (paused() || document.hidden) return;
            lens.classList.remove('is-scanning');
            void lens.offsetWidth;
            lens.classList.add('is-scanning');
            window.dispatchEvent(new CustomEvent('site:scan'));
        };
        lens.addEventListener('animationend', (event) => {
            if (event.animationName === 'frame-scan') lens.classList.remove('is-scanning');
        });
        const first = () => window.setTimeout(scan, 380);
        if (!root.classList.contains('no-intro')) {
            if (root.classList.contains('is-loaded')) first();
            else {
                const watcher = new MutationObserver(() => {
                    if (!root.classList.contains('is-loaded')) return;
                    watcher.disconnect();
                    first();
                });
                watcher.observe(root, { attributes: true, attributeFilter: ['class'] });
            }
        }
        if (!finePointer.matches) return;
        lens.addEventListener('pointerenter', () => { if (!lens.classList.contains('is-scanning')) scan(); });
        let frame = 0;
        let tiltX = 0;
        let tiltY = 0;
        const apply = () => {
            frame = 0;
            lens.style.setProperty('--lx', `${tiltX.toFixed(2)}deg`);
            lens.style.setProperty('--ly', `${tiltY.toFixed(2)}deg`);
        };
        hero.addEventListener('pointermove', (event) => {
            if (paused()) return;
            const rect = lens.getBoundingClientRect();
            const dx = (event.clientX - (rect.left + rect.width / 2)) / window.innerWidth;
            const dy = (event.clientY - (rect.top + rect.height / 2)) / window.innerHeight;
            tiltY = Math.max(-1, Math.min(1, dx * 2)) * 5;
            tiltX = Math.max(-1, Math.min(1, dy * 2)) * -4;
            if (!frame) frame = requestAnimationFrame(apply);
        });
        hero.addEventListener('pointerleave', () => {
            tiltX = 0;
            tiltY = 0;
            if (!frame) frame = requestAnimationFrame(apply);
        });
    }

    /* The land behind the hero is alive. Contour lines trace a terrain that slowly shifts, data
       points travel along them, the ground rises under the pointer, and a pulse ripples out from
       the portrait whenever it is scanned. The static contour drawing stays in place without
       JavaScript, with reduced motion, and until the first live frame is ready. */
    function terrain() {
        const hero = $('.hero');
        const frame = $('[data-lens]');
        if (!hero || !frame || reduceQuery.matches || typeof Path2D !== 'function') return;
        const canvas = document.createElement('canvas');
        canvas.className = 'terrain';
        canvas.setAttribute('aria-hidden', 'true');
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        hero.prepend(canvas);
        const rtl = root.dir === 'rtl';
        const LEVELS = 20;
        const L0 = 0.05;
        const DL = (1.3 - L0) / (LEVELS - 1);
        const STYLES = [
            ['rgba(118,192,158,.78)', 1], ['rgba(134,178,222,.78)', 1],
            ['rgba(92,174,139,.92)', 1.7], ['rgba(104,156,210,.92)', 1.7]
        ];
        let w = 0, h = 0, dpr = 1, cs = 12, nx = 0, ny = 0;
        let fade = null, fadeX = 1;
        let field = null, base = null, summit = null, dist = null;
        let cx = 0, cy = 0;
        let particles = [];
        let running = false, raf = 0, last = 0, clock = 0, born = -1, lastInput = 0;
        let onScreen = true;
        const pointer = { x: -9999, y: -9999, tx: -9999, ty: -9999, a: 0, ta: 0 };
        const ripples = [];

        const gauss = (dx, dy, sx, sy) => Math.exp(-((dx * dx) / (sx * sx) + (dy * dy) / (sy * sy)));
        const measure = () => {
            const box = canvas.getBoundingClientRect();
            if (!box.width || !box.height) return false;
            dpr = Math.min(window.devicePixelRatio || 1, 1.5);
            w = box.width; h = box.height;
            canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
            cs = w < 700 ? 15 : 12;
            nx = Math.ceil(w / cs) + 2; ny = Math.ceil(h / cs) + 2;
            const fr = frame.getBoundingClientRect();
            cx = fr.left + fr.width / 2 - box.left;
            cy = fr.top + fr.height * 0.46 - box.top;
            const n = nx * ny;
            field = new Float32Array(n); base = new Float32Array(n); summit = new Float32Array(n); dist = new Float32Array(n);
            // One summit under the portrait and two lower hills; on one-column layouts they stack around it
            const narrow = w < 961;
            const sx = narrow ? Math.max(220, w * 0.62) : Math.max(280, Math.min(w * 0.38, 580));
            const sy = narrow ? Math.max(300, Math.min(h * 0.24, 460)) : Math.max(260, h * 0.5);
            const bx = rtl ? w * (narrow ? 0.86 : 0.84) : w * (narrow ? 0.14 : 0.16);
            const by = narrow ? cy + Math.min(h * 0.3, 640) : h * 0.9;
            const tx = narrow ? w * (rtl ? 0.35 : 0.65) : w * 0.48, ty = narrow ? cy - Math.min(h * 0.28, 560) : -h * 0.02;
            for (let j = 0; j < ny; j += 1) {
                for (let i = 0; i < nx; i += 1) {
                    const x = i * cs, y = j * cs, k = j * nx + i;
                    summit[k] = gauss(x - cx, y - cy, sx, sy);
                    base[k] = 0.62 * gauss(x - bx, y - by, narrow ? 260 : 340, narrow ? 300 : 270) + 0.3 * gauss(x - tx, y - ty, narrow ? 280 : 360, 230);
                    dist[k] = Math.hypot(x - cx, y - cy);
                }
            }
            // The land fades out toward the words: an elliptical window centred on the portrait
            const rx = w * (narrow ? 0.74 : 0.62), ry = h * (narrow ? 0.46 : 0.78);
            fadeX = rx / ry;
            fade = ctx.createRadialGradient(0, 0, 0, 0, 0, ry);
            fade.addColorStop(0, '#000');
            fade.addColorStop(0.2, '#000');
            fade.addColorStop(0.55, 'rgba(0,0,0,.45)');
            fade.addColorStop(0.86, 'rgba(0,0,0,0)');
            fade.addColorStop(1, 'rgba(0,0,0,0)');
            const count = Math.round(Math.min(130, Math.max(36, (w * h) / 10000)));
            particles = Array.from({ length: count }, () => spawn({}, true));
            return true;
        };
        const height = (x, y, t) =>
            0.034 * Math.sin(x / 97 + y / 143 + t * 0.21) + 0.024 * Math.sin(x / 61 - y / 83 + 1.3 - t * 0.17) + 0.017 * Math.sin((x + y) / 41 + t * 0.29);
        const compute = (t) => {
            const breathe = 1 + 0.045 * Math.sin(t * 0.33);
            for (let j = 0; j < ny; j += 1) {
                const y = j * cs;
                for (let i = 0; i < nx; i += 1) {
                    const k = j * nx + i;
                    field[k] = summit[k] * breathe + base[k] + height(i * cs, y, t);
                }
            }
            if (pointer.a > 0.002) {
                const r = 130, reach = Math.ceil((r * 2.6) / cs);
                const pi = Math.round(pointer.x / cs), pj = Math.round(pointer.y / cs);
                for (let j = Math.max(0, pj - reach); j < Math.min(ny, pj + reach); j += 1) {
                    for (let i = Math.max(0, pi - reach); i < Math.min(nx, pi + reach); i += 1) {
                        field[j * nx + i] += pointer.a * gauss(i * cs - pointer.x, j * cs - pointer.y, r, r);
                    }
                }
            }
            for (let q = ripples.length - 1; q >= 0; q -= 1) {
                const ripple = ripples[q];
                const age = t - ripple.t;
                const radius = age * 430;
                if (radius > Math.hypot(w, h)) { ripples.splice(q, 1); continue; }
                const amp = 0.2 * Math.max(0, 1 - age / 2.6);
                const local = Number.isFinite(ripple.x);
                for (let k = 0; k < field.length; k += 1) {
                    const away = local ? Math.hypot((k % nx) * cs - ripple.x, Math.floor(k / nx) * cs - ripple.y) : dist[k];
                    const d = away - radius;
                    if (d > -120 && d < 120) field[k] += amp * Math.exp(-(d * d) / 2500);
                }
            }
        };
        const paths = () => {
            const out = [new Path2D(), new Path2D(), new Path2D(), new Path2D()];
            for (let j = 0; j < ny - 1; j += 1) {
                for (let i = 0; i < nx - 1; i += 1) {
                    const k = j * nx + i;
                    const a = field[k], b = field[k + 1], c = field[k + nx + 1], d = field[k + nx];
                    const lo = Math.min(a, b, c, d), hi = Math.max(a, b, c, d);
                    let first = Math.ceil((lo - L0) / DL), end = Math.floor((hi - L0) / DL);
                    if (first < 0) first = 0;
                    if (end > LEVELS - 1) end = LEVELS - 1;
                    if (end < first) continue;
                    const x0 = i * cs, y0 = j * cs;
                    for (let n = first; n <= end; n += 1) {
                        const level = L0 + n * DL;
                        const code = (a > level ? 8 : 0) | (b > level ? 4 : 0) | (c > level ? 2 : 0) | (d > level ? 1 : 0);
                        if (code === 0 || code === 15) continue;
                        const top = () => [x0 + (cs * (level - a)) / (b - a), y0];
                        const right = () => [x0 + cs, y0 + (cs * (level - b)) / (c - b)];
                        const bottom = () => [x0 + (cs * (level - d)) / (c - d), y0 + cs];
                        const left = () => [x0, y0 + (cs * (level - a)) / (d - a)];
                        const path = out[(n % 5 === 4 ? 2 : 0) + (n % 2)];
                        const seg = (p, q) => { path.moveTo(p[0], p[1]); path.lineTo(q[0], q[1]); };
                        switch (code) {
                            case 1: case 14: seg(left(), bottom()); break;
                            case 2: case 13: seg(bottom(), right()); break;
                            case 3: case 12: seg(left(), right()); break;
                            case 4: case 11: seg(top(), right()); break;
                            case 6: case 9: seg(top(), bottom()); break;
                            case 7: case 8: seg(left(), top()); break;
                            case 5: if ((a + b + c + d) / 4 > level) { seg(left(), bottom()); seg(top(), right()); } else { seg(left(), top()); seg(bottom(), right()); } break;
                            case 10: if ((a + b + c + d) / 4 > level) { seg(left(), top()); seg(bottom(), right()); } else { seg(left(), bottom()); seg(top(), right()); } break;
                            default: break;
                        }
                    }
                }
            }
            return out;
        };
        const slope = (x, y) => {
            const gx = x / cs, gy = y / cs;
            const i = Math.floor(gx), j = Math.floor(gy);
            if (i < 0 || j < 0 || i >= nx - 1 || j >= ny - 1) return null;
            const fx = gx - i, fy = gy - j, k = j * nx + i;
            const a = field[k], b = field[k + 1], c = field[k + nx + 1], d = field[k + nx];
            return [((b - a) * (1 - fy) + (c - d) * fy) / cs, ((d - a) * (1 - fx) + (c - b) * fx) / cs, a + (b - a) * fx + (d - a) * fy];
        };
        function spawn(p, anywhere) {
            for (let tries = 0; tries < 24; tries += 1) {
                const x = Math.random() * w, y = Math.random() * h;
                const k = Math.min(ny - 1, Math.round(y / cs)) * nx + Math.min(nx - 1, Math.round(x / cs));
                const value = (summit ? summit[k] : 0) + (base ? base[k] : 0);
                if (value > 0.16 && Math.random() < value) {
                    p.x = x; p.y = y; break;
                }
            }
            if (!Number.isFinite(p.x)) { p.x = cx + (Math.random() - 0.5) * 300; p.y = cy + (Math.random() - 0.5) * 300; }
            p.life = anywhere ? Math.random() * 5 : 0;
            p.span = 4 + Math.random() * 4;
            p.speed = 16 + Math.random() * 22;
            p.dir = Math.random() < 0.5 ? -1 : 1;
            p.vx = 0; p.vy = 0;
            return p;
        }
        const move = (dt) => {
            for (const p of particles) {
                p.life += dt;
                const g = slope(p.x, p.y);
                if (!g || p.life > p.span) { spawn(p, false); continue; }
                const mag = Math.hypot(g[0], g[1]);
                if (mag < 1e-5) { spawn(p, false); continue; }
                const tx = (-g[1] / mag) * p.dir, ty = (g[0] / mag) * p.dir;
                const speed = p.speed * (0.7 + Math.min(1.6, mag * 260));
                p.vx = tx * speed; p.vy = ty * speed;
                p.x += p.vx * dt; p.y += p.vy * dt;
            }
        };
        const draw = (t) => {
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.clearRect(0, 0, w, h);
            ctx.lineCap = 'round';
            const out = paths();
            out.forEach((path, n) => {
                ctx.strokeStyle = STYLES[n][0];
                ctx.lineWidth = STYLES[n][1];
                ctx.stroke(path);
            });
            // Lines near the pointer catch the light
            if (pointer.a > 0.01) {
                ctx.globalCompositeOperation = 'source-atop';
                const light = ctx.createRadialGradient(pointer.x, pointer.y, 0, pointer.x, pointer.y, 190);
                light.addColorStop(0, `rgba(11,106,122,${(0.95 * pointer.a / 0.3).toFixed(3)})`);
                light.addColorStop(1, 'rgba(11,106,122,0)');
                ctx.fillStyle = light;
                ctx.fillRect(pointer.x - 200, pointer.y - 200, 400, 400);
                ctx.globalCompositeOperation = 'source-over';
            }
            // Data points travelling along the lines
            for (const p of particles) {
                const fade = Math.min(1, p.life / 0.7, (p.span - p.life) / 0.7);
                if (fade <= 0) continue;
                ctx.strokeStyle = `rgba(28,117,82,${(0.34 * fade).toFixed(3)})`;
                ctx.lineWidth = 1.4;
                ctx.beginPath();
                ctx.moveTo(p.x - p.vx * 0.6, p.y - p.vy * 0.6);
                ctx.lineTo(p.x, p.y);
                ctx.stroke();
                ctx.fillStyle = `rgba(11,106,122,${(0.85 * fade).toFixed(3)})`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, 1.8, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.globalCompositeOperation = 'destination-in';
            ctx.save();
            ctx.translate(cx, cy);
            ctx.scale(fadeX, 1);
            ctx.fillStyle = fade;
            ctx.fillRect(-w * 2, -h * 2, w * 4, h * 4);
            ctx.restore();
            ctx.globalCompositeOperation = 'source-over';
            // On arrival the land draws itself outward from the portrait
            const age = t - born;
            if (age < 2.2) {
                const reach = age * 900;
                ctx.globalCompositeOperation = 'destination-in';
                const reveal = ctx.createRadialGradient(cx, cy, 0, cx, cy, reach + 1);
                reveal.addColorStop(0, '#000');
                reveal.addColorStop(Math.max(0, 1 - 220 / (reach + 1)), '#000');
                reveal.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = reveal;
                ctx.fillRect(0, 0, w, h);
                ctx.globalCompositeOperation = 'source-over';
            }
        };
        const step = (now) => {
            raf = 0;
            if (!running) return;
            raf = requestAnimationFrame(step);
            // About 30 frames a second while someone is interacting, 15 once the page has been still for a while
            if (last && now - last < (clock - lastInput > 12 ? 64 : 31)) return;
            const dt = last ? Math.min((now - last) / 1000, 0.06) : 0.016;
            last = now;
            clock += dt;
            if (born < 0) born = clock;
            pointer.x += (pointer.tx - pointer.x) * Math.min(1, dt * 7);
            pointer.y += (pointer.ty - pointer.y) * Math.min(1, dt * 7);
            pointer.a += (pointer.ta - pointer.a) * Math.min(1, dt * 3);
            compute(clock);
            move(dt);
            draw(clock);
            if (!canvas.classList.contains('is-live')) {
                canvas.classList.add('is-live');
                root.classList.add('terrain-live');
            }
        };
        const allowed = () => onScreen && !document.hidden && !paused() && !asking();
        const sync = () => {
            const go = allowed() && w > 0;
            if (go && !running) { running = true; last = 0; raf = requestAnimationFrame(step); }
            if (!go && running) { running = false; if (raf) cancelAnimationFrame(raf); raf = 0; }
        };
        const start = () => {
            if (!measure()) return;
            sync();
        };
        hero.addEventListener('pointermove', (event) => {
            if (event.pointerType === 'touch') return;
            const box = canvas.getBoundingClientRect();
            pointer.tx = event.clientX - box.left; pointer.ty = event.clientY - box.top;
            if (pointer.a < 0.01 && pointer.ta === 0) { pointer.x = pointer.tx; pointer.y = pointer.ty; }
            pointer.ta = 0.3;
            lastInput = clock;
        }, { passive: true });
        hero.addEventListener('pointerleave', () => { pointer.ta = 0; });
        hero.addEventListener('pointerdown', (event) => {
            if (event.pointerType !== 'touch' || event.target.closest('a, button, input')) return;
            const box = canvas.getBoundingClientRect();
            ripples.push({ t: clock, x: event.clientX - box.left, y: event.clientY - box.top });
            lastInput = clock;
        }, { passive: true });
        window.addEventListener('site:scan', () => { if (running) { ripples.push({ t: clock }); lastInput = clock; } });
        window.addEventListener('scroll', () => { lastInput = clock; }, { passive: true });
        if ('ResizeObserver' in window) {
            let pending = 0;
            new ResizeObserver(() => {
                window.clearTimeout(pending);
                pending = window.setTimeout(() => { if (measure()) sync(); }, 120);
            }).observe(hero);
        }
        if ('IntersectionObserver' in window) {
            new IntersectionObserver((entries) => { onScreen = entries[0].isIntersecting; sync(); }).observe(hero);
        }
        document.addEventListener('visibilitychange', sync);
        onMotion(sync);
        reduceQuery.addEventListener('change', () => { if (reduceQuery.matches) { running = false; canvas.remove(); root.classList.remove('terrain-live'); } });
        // Begin once the page has painted its words and portrait
        const begin = () => window.setTimeout(start, 240);
        if (root.classList.contains('is-loaded')) begin();
        else {
            const watcher = new MutationObserver(() => {
                if (!root.classList.contains('is-loaded')) return;
                watcher.disconnect();
                begin();
            });
            watcher.observe(root, { attributes: true, attributeFilter: ['class'] });
        }
    }

    /* Cards catch a soft light where the pointer is and their edge brightens nearby; the name
       brightens to lagoon teal under the pointer. */
    function spotlight() {
        if (!finePointer.matches) return;
        $$('.venture, .work-card, .capability, .feature, .guide-tile, .hero-name').forEach((element) => {
            let frame = 0;
            let x = 0;
            let y = 0;
            element.addEventListener('pointermove', (event) => {
                const rect = element.getBoundingClientRect();
                x = event.clientX - rect.left;
                y = event.clientY - rect.top;
                if (!frame) {
                    frame = requestAnimationFrame(() => {
                        frame = 0;
                        element.style.setProperty('--mx', `${x.toFixed(0)}px`);
                        element.style.setProperty('--my', `${y.toFixed(0)}px`);
                    });
                }
            }, { passive: true });
            element.addEventListener('pointerleave', () => { element.style.setProperty('--mx', '-999px'); });
        });
    }

    /* Section names resolve from scrambled signal into words the first time they come into view. */
    function decode() {
        if (root.dir === 'rtl' || reduceQuery.matches || !('IntersectionObserver' in window)) return;
        const labels = $$('.section-label');
        const glyphs = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789+/=';
        const run = (label) => {
            const text = label.textContent;
            if (paused() || !text.trim()) return;
            const range = document.createRange();
            range.selectNodeContents(label);
            const width = range.getBoundingClientRect().width;
            const quiet = document.createElement('span');
            quiet.className = 'sr-only';
            quiet.textContent = text;
            const shown = document.createElement('span');
            shown.setAttribute('aria-hidden', 'true');
            shown.className = 'decoding';
            label.replaceChildren(quiet, shown);
            // Hold the width of the final words so the survey line does not jump while letters settle
            shown.style.width = `${Math.ceil(width)}px`;
            const started = performance.now();
            const duration = 420 + text.length * 22;
            const tick = (now) => {
                const progress = Math.min(1, (now - started) / duration);
                const fixed = Math.floor(progress * text.length);
                let out = text.slice(0, fixed);
                for (let i = fixed; i < text.length; i += 1) out += text[i] === ' ' ? ' ' : glyphs[(Math.random() * glyphs.length) | 0];
                shown.textContent = out;
                if (progress < 1) requestAnimationFrame(tick);
                else label.textContent = text;
            };
            requestAnimationFrame(tick);
        };
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                observer.unobserve(entry.target);
                run(entry.target);
            });
        }, { threshold: 0.8 });
        labels.forEach((label) => observer.observe(label));
    }

    /* Once the Ask bar in the hero has scrolled away, Ask waits in the corner. On touch screens it
       steps aside while you scroll down and returns when you scroll up. Measured on scroll, so jumps
       to a section (which skip past the hero) are handled too. */
    function floatingAsk() {
        const inline = $('.ask-inline');
        const floating = $('.ask-floating');
        if (!inline || !floating || floating.hidden) return;
        const touch = !finePointer.matches;
        let tucked = false;
        let lastY = window.scrollY;
        let frame = 0;
        const update = () => {
            frame = 0;
            const y = window.scrollY;
            if (touch && Math.abs(y - lastY) >= 10) {
                tucked = y > lastY && y > 0;
                lastY = y;
            }
            const past = inline.getBoundingClientRect().bottom < 0;
            floating.classList.toggle('is-visible', past && !tucked);
        };
        const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
        window.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', schedule, { passive: true });
        update();
    }

    /* Buttons lean toward the pointer. */
    function magnetic() {
        if (!finePointer.matches) return;
        $$('[data-magnetic]').forEach((element) => {
            let rect = null;
            let frame = 0;
            let x = 0;
            let y = 0;
            element.addEventListener('pointerenter', () => { rect = element.getBoundingClientRect(); });
            element.addEventListener('pointermove', (event) => {
                if (paused() || !rect) return;
                x = (event.clientX - (rect.left + rect.width / 2)) * 0.2;
                y = (event.clientY - (rect.top + rect.height / 2)) * 0.32;
                if (!frame) {
                    frame = requestAnimationFrame(() => {
                        frame = 0;
                        element.style.setProperty('--tx', `${x.toFixed(1)}px`);
                        element.style.setProperty('--ty', `${y.toFixed(1)}px`);
                    });
                }
            });
            element.addEventListener('pointerleave', () => {
                rect = null;
                element.style.setProperty('--tx', '0px');
                element.style.setProperty('--ty', '0px');
            });
        });
    }

    /* The Appraiva console runs its four layers in a loop while it is on screen. */
    function agentRun() {
        const run = $('.agent-run');
        if (!run) return;
        const steps = $$('[data-step]', run);
        const show = (frame) => {
            run.dataset.phase = String(frame);
            steps.forEach((step, index) => {
                step.dataset.state = index < frame ? 'done' : index === frame ? 'running' : 'idle';
            });
        };
        let frame = 0;
        let timer = 0;
        let onScreen = false;
        const stop = () => { window.clearTimeout(timer); timer = 0; };
        const next = () => {
            timer = 0;
            frame = frame >= steps.length ? 0 : frame + 1;
            show(frame);
            schedule();
        };
        const schedule = () => {
            if (timer || !onScreen || paused()) return;
            timer = window.setTimeout(next, frame >= steps.length ? 3400 : 1400);
        };
        const sync = () => {
            if (reduceQuery.matches) {
                stop();
                frame = steps.length;
                show(frame);
                return;
            }
            if (!onScreen || paused()) stop(); else schedule();
        };
        if ('IntersectionObserver' in window) {
            new IntersectionObserver((entries) => { onScreen = entries[0].isIntersecting; sync(); }, { threshold: 0.35 }).observe(run);
        } else {
            onScreen = true;
        }
        onMotion(sync);
        show(reduceQuery.matches ? steps.length : 0);
        sync();
    }

    /* The experience log fills as you read it. */
    function timeline() {
        const log = $('[data-timeline]');
        if (!log) return;
        const items = $$('.timeline-item', log);
        let frame = 0;
        const update = () => {
            frame = 0;
            const line = window.innerHeight * 0.62;
            const rect = log.getBoundingClientRect();
            const progress = Math.min(1, Math.max(0, (line - rect.top) / rect.height));
            log.style.setProperty('--progress', progress.toFixed(3));
            items.forEach((item) => item.classList.toggle('is-passed', item.getBoundingClientRect().top + 40 < line));
        };
        const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
        window.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', schedule, { passive: true });
        update();
    }

    /* Siblings that appear together arrive one after another. */
    function stagger() {
        ['.ventures', '.work-grid', '.writing-layout'].forEach((selector) => {
            const parent = $(selector);
            if (!parent) return;
            Array.from(parent.children).filter((child) => child.classList.contains('reveal')).forEach((child, index) => {
                child.style.setProperty('--reveal-delay', `${index * 110}ms`);
            });
        });
    }

    /* Decorative loops pause while their part of the page is off screen. */
    function offscreen() {
        if (!('IntersectionObserver' in window)) return;
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => entry.target.classList.toggle('is-offscreen', !entry.isIntersecting));
        }, { rootMargin: '120px 0px' });
        $$('.hero, .hero-visual, .ventures, .agent-run, .work-grid, .guide-tile, .contact').forEach((target) => observer.observe(target));
    }

    /* Keep the Ask panel's motion item in step with the motion toggle. */
    function motionCommand() {
        const item = $('[data-motion-command]');
        const toggle = $('.motion-toggle');
        if (!item || !toggle) return;
        const sync = () => {
            item.textContent = toggle.textContent;
            item.dataset.unavailable = toggle.hidden ? 'true' : 'false';
            item.dataset.paused = toggle.dataset.paused === 'true' ? 'true' : 'false';
            if (toggle.hidden) item.hidden = true;
        };
        onMotion(sync);
        sync();
    }

    [clock, askPanel, copyEmail, navGlow, lensTilt, terrain, spotlight, decode, floatingAsk, magnetic, agentRun, timeline, stagger, offscreen, motionCommand].forEach((feature) => {
        try {
            feature();
        } catch (error) {
            if (window.console) console.warn('[a-samadi.com]', feature.name, error);
        }
    });
})();
