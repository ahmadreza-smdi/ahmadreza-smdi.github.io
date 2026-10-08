/* Intelligence engine for the homepage.
   Dubai clock, the Ask panel (it searches this page and streams back the best passage), the
   capabilities orbiting the portrait lens, and a few small agentic details.
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

    /* The edge of the screen lights up while the site is answering. */
    let glowTimer = 0;
    const glow = (duration) => {
        window.clearTimeout(glowTimer);
        root.classList.add('is-glowing');
        glowTimer = window.setTimeout(() => root.classList.remove('is-glowing'), duration);
    };

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
        if (input) input.placeholder = i18n('search', 'Ask about my work or jump to a section');

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
                const paragraphs = place.matches('p') ? [place] : $$('p', place).filter((p) => !p.matches('.section-label, .card-topline, .topic, .copy-status') && clean(p).length > 24);
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
            if (current && current.entry === entry && current.excerpt === excerpt) {
                answer.hidden = false;
                return;
            }
            current = { entry, excerpt };
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
            empty.hidden = found || Boolean(match);
            answerTimer = window.setTimeout(() => { showAnswer(match); settleActive(); }, current ? 160 : 60);
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
            announce(true);
            input.focus();
        };
        const close = () => { if (dialog.open) dialog.close(); };
        dialog.addEventListener('close', () => {
            announce(false);
            if (!keepFocus && lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus({ preventScroll: true });
            keepFocus = false;
        });
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
                const target = current && current.entry.element;
                if (!target) return;
                glow(1900);
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
        const write = async () => {
            try {
                await navigator.clipboard.writeText(email);
                return true;
            } catch (error) {
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
        buttons.forEach((button) => button.addEventListener('click', async () => {
            if (button.classList.contains('is-copied')) return;
            const copied = await write();
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
            if (button.classList.contains('command-item')) {
                if (!button.dataset.label) button.dataset.label = button.textContent;
                const label = button.dataset.label;
                button.textContent = message;
                button.classList.add('is-copied');
                window.setTimeout(() => {
                    button.textContent = label;
                    button.classList.remove('is-copied');
                    const dialog = button.closest('dialog');
                    if (dialog && dialog.open) dialog.close();
                }, 900);
            }
        }));
    }

    /* The soft pill that follows the hovered or current section link. */
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

    /* Four things I work on orbit the portrait. They pass behind the lens and in front of it, shrinking
       and dimming with depth, and on narrow screens they keep inside the viewport. */
    function orbit() {
        const visual = $('.hero-visual');
        const lens = visual && $('.lens', visual);
        const chips = visual ? $$('.orbit li', visual) : [];
        if (!lens || !chips.length) return;
        const start = [205, 335, 25, 155].map((degrees) => degrees * Math.PI / 180);
        const period = 48000;
        let geometry = null;
        let raf = 0;
        let onScreen = true;
        let elapsed = 0;
        let last = 0;
        const hero = visual.closest('.hero');
        const measure = () => {
            const style = getComputedStyle(visual);
            const size = lens.offsetWidth;
            const rect = visual.getBoundingClientRect();
            const widths = chips.map((chip) => chip.offsetWidth);
            // The ring may reach into the gap beside the copy, never past it.
            const gap = hero ? parseFloat(getComputedStyle(hero).columnGap) || 0 : 0;
            const natural = size * (parseFloat(style.getPropertyValue('--rx-k')) || 0.62);
            const reach = visual.offsetWidth / 2 + gap - Math.max(...widths) / 2;
            const rx = Math.min(natural, Math.max(size * 0.56, reach));
            visual.style.setProperty('--rx', `${rx.toFixed(1)}px`);
            geometry = {
                rx,
                ry: size * (parseFloat(style.getPropertyValue('--ry-k')) || 0.19),
                cos: parseFloat(style.getPropertyValue('--tc')) || 1,
                sin: parseFloat(style.getPropertyValue('--ts')) || 0,
                centre: rect.left + rect.width / 2,
                width: document.documentElement.clientWidth,
                widths
            };
        };
        const place = () => {
            if (!geometry) measure();
            const { rx, ry, cos, sin, centre, width, widths } = geometry;
            const turn = (elapsed / period) * Math.PI * 2;
            chips.forEach((chip, index) => {
                const angle = start[index] - turn;
                const depth = Math.sin(angle);
                const scale = depth >= 0 ? 0.96 + 0.04 * depth : 0.96 + 0.1 * depth;
                const half = (widths[index] * scale) / 2;
                const min = 10 + half - centre;
                const max = width - 10 - half - centre;
                // A point on the ellipse, turned by the ring's tilt.
                const ox = Math.cos(angle) * rx;
                const oy = depth * ry;
                let x = ox * cos - oy * sin;
                const y = ox * sin + oy * cos;
                if (min < max) x = Math.min(max, Math.max(min, x));
                chip.style.transform = `translate(-50%, -50%) translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) scale(${scale.toFixed(3)})`;
                chip.style.opacity = (depth >= 0 ? 1 : 1 + depth * 0.55).toFixed(3);
                chip.style.zIndex = depth >= 0 ? '4' : '1';
            });
        };
        const loop = (now) => {
            raf = 0;
            if (!onScreen || paused() || asking()) {
                last = 0;
                return;
            }
            if (last) elapsed += Math.min(now - last, 64);
            last = now;
            place();
            raf = requestAnimationFrame(loop);
        };
        const kick = () => {
            if (!raf && onScreen && !paused() && !asking()) raf = requestAnimationFrame(loop);
        };
        const refresh = () => { measure(); place(); kick(); };
        if ('ResizeObserver' in window) {
            const observer = new ResizeObserver(refresh);
            observer.observe(visual);
            chips.forEach((chip) => observer.observe(chip));
        }
        window.addEventListener('resize', refresh, { passive: true });
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(refresh);
        if ('IntersectionObserver' in window) {
            new IntersectionObserver((entries) => { onScreen = entries[0].isIntersecting; kick(); }).observe(visual);
        }
        onMotion(kick);
        measure();
        place();
        kick();
    }

    /* The lens leans a little toward the pointer. */
    function lensTilt() {
        const hero = $('.hero');
        const lens = $('[data-lens]');
        if (!hero || !lens || !finePointer.matches) return;
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
            tiltY = Math.max(-1, Math.min(1, dx * 2)) * 9;
            tiltX = Math.max(-1, Math.min(1, dy * 2)) * -7;
            if (!frame) frame = requestAnimationFrame(apply);
        });
        hero.addEventListener('pointerleave', () => {
            tiltX = 0;
            tiltY = 0;
            if (!frame) frame = requestAnimationFrame(apply);
        });
    }

    /* Once the Ask bar in the hero scrolls away, a compact one waits at the bottom of the screen.
       On touch screens it steps aside while you scroll down and returns when you scroll up. */
    function floatingAsk() {
        const inline = $('.ask-inline');
        const floating = $('.ask-floating');
        if (!inline || !floating || floating.hidden || !('IntersectionObserver' in window)) return;
        let past = false;
        let tucked = false;
        const sync = () => floating.classList.toggle('is-visible', past && !tucked);
        new IntersectionObserver((entries) => {
            const entry = entries[0];
            past = !entry.isIntersecting && entry.boundingClientRect.top < 0;
            sync();
        }).observe(inline);
        if (finePointer.matches) return;
        let lastY = window.scrollY;
        let frame = 0;
        window.addEventListener('scroll', () => {
            if (frame) return;
            frame = requestAnimationFrame(() => {
                frame = 0;
                const y = window.scrollY;
                if (Math.abs(y - lastY) < 10) return;
                tucked = y > lastY && y > 0;
                lastY = y;
                sync();
            });
        }, { passive: true });
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
        $$('.hero-copy, .hero-visual, .hero-foot, .ventures, .agent-run, .work-grid, .guide-tile, .contact').forEach((target) => observer.observe(target));
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

    [clock, askPanel, copyEmail, navGlow, orbit, lensTilt, floatingAsk, magnetic, agentRun, timeline, stagger, offscreen, motionCommand].forEach((feature) => {
        try {
            feature();
        } catch (error) {
            if (window.console) console.warn('[a-samadi.com]', feature.name, error);
        }
    });
})();
