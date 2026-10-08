/* Pastel Hologram engine for the homepage.
   Aurora wallpaper, Dubai clock, command menu, hero choreography and small "agentic" details.
   Everything here is an enhancement: without this file the page is complete and readable. */
(() => {
    'use strict';
    const root = document.documentElement;
    const rtl = root.dir === 'rtl';
    const lang = root.lang || 'en';
    const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const $ = (selector, scope = document) => scope.querySelector(selector);
    const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
    const paused = () => reduceQuery.matches || root.classList.contains('motion-paused');
    const i18n = (key, fallback) => {
        const node = document.querySelector(`[data-i18n="${key}"]`);
        return node ? node.textContent.trim() : fallback;
    };
    const motionListeners = [];
    const onMotion = (listener) => motionListeners.push(listener);
    window.addEventListener('site:motion', (event) => motionListeners.forEach((listener) => listener(event.detail || {})));

    /* Aurora: a slow, domain-warped pastel mesh rendered at reduced resolution. */
    function aurora() {
        const canvas = $('.aurora');
        if (!canvas) return;
        const setVeil = () => {
            const amount = Math.min(1, Math.max(0, window.scrollY / (window.innerHeight * 0.9)));
            canvas.style.opacity = String(1 - amount * 0.5);
        };
        let veilFrame = 0;
        window.addEventListener('scroll', () => {
            if (!veilFrame) veilFrame = requestAnimationFrame(() => { veilFrame = 0; setVeil(); });
        }, { passive: true });
        setVeil();

        let gl = null;
        try {
            gl = canvas.getContext('webgl', { alpha: false, antialias: false, depth: false, stencil: false, preserveDrawingBuffer: false, powerPreference: 'low-power' });
        } catch (error) { gl = null; }
        if (!gl) return;

        const vertexSource = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
        const fragmentSource = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform vec2 r;uniform float t;uniform vec2 m;uniform float k;
float h(vec2 p){vec3 q=fract(vec3(p.xyx)*.1031);q+=dot(q,q.yzx+33.33);return fract((q.x+q.y)*q.z);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1.,0.)),f.x),mix(h(i+vec2(0.,1.)),h(i+vec2(1.,1.)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*n(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
vec3 blob(vec2 p,vec2 c,vec3 col,float rad,inout float w){vec2 d=p-c;float g=exp(-dot(d,d)/(rad*rad));w+=g;return col*g;}
void main(){
 vec2 uv=gl_FragCoord.xy/r;vec2 e=r/min(r.x,r.y);vec2 p=uv*e;float s=t*.05;
 vec2 warp=vec2(fbm(p*1.5+vec2(s,-s*.7)),fbm(p*1.5+vec2(-s*.8,s)+4.3))-.5;
 vec2 q=p+warp*.6;float w=0.;vec3 c=vec3(0.);
 c+=blob(q,vec2(.16,.80)*e+vec2(.07*sin(s*1.3),.06*cos(s)),vec3(.79,.73,1.),.44,w);
 c+=blob(q,vec2(.86,.86)*e+vec2(.06*cos(s*1.1),.05*sin(s*1.7)),vec3(.68,.86,1.),.42,w);
 c+=blob(q,vec2(.76,.14)*e+vec2(.07*sin(s*.9+1.),.06*cos(s*1.2)),vec3(.62,.93,.82),.46,w);
 c+=blob(q,vec2(.14,.10)*e+vec2(.07*cos(s*.8+2.),.05*sin(s)),vec3(1.,.79,.70),.42,w);
 c+=blob(q,vec2(.50,.48)*e+vec2(.12*sin(s*.7+3.),.10*cos(s*.6)),vec3(1.,.93,.64),.30,w);
 c+=blob(q,vec2(.44,.98)*e+vec2(.10*cos(s*.5+4.),0.),vec3(1.,.78,.90),.30,w);
 vec3 col=c/max(w,.001);float l=dot(col,vec3(.299,.587,.114));col=clamp(mix(vec3(l),col,1.3),0.,1.);
 float cover=clamp(w,0.,1.);
 vec2 d=p-m*e;float g=exp(-dot(d,d)*7.);
 col=mix(col,vec3(1.,.95,.74),g*.55);cover=max(cover,g*.7);
 vec3 o=mix(vec3(.965,.965,.992),col,cover*k);
 o+=(h(gl_FragCoord.xy+fract(t*.37)*91.)-.5)*.022;
 gl_FragColor=vec4(o,1.);
}`;
        const compile = (type, source) => {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
        };
        const vertex = compile(gl.VERTEX_SHADER, vertexSource);
        const fragment = compile(gl.FRAGMENT_SHADER, fragmentSource);
        if (!vertex || !fragment) return;
        const program = gl.createProgram();
        gl.attachShader(program, vertex);
        gl.attachShader(program, fragment);
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
        gl.useProgram(program);
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
        const position = gl.getAttribLocation(program, 'p');
        gl.enableVertexAttribArray(position);
        gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
        const uniform = { r: gl.getUniformLocation(program, 'r'), t: gl.getUniformLocation(program, 't'), m: gl.getUniformLocation(program, 'm'), k: gl.getUniformLocation(program, 'k') };

        const small = window.matchMedia('(max-width: 760px)');
        const seed = Math.random() * 400;
        const pointer = { x: 0.72, y: 0.7, tx: 0.72, ty: 0.7 };
        let raf = 0;
        let last = 0;
        let lost = false;
        const resize = () => {
            const scale = small.matches ? 0.35 : 0.5;
            const width = Math.max(2, Math.round(window.innerWidth * scale));
            const height = Math.max(2, Math.round(window.innerHeight * scale));
            if (canvas.width !== width || canvas.height !== height) {
                canvas.width = width;
                canvas.height = height;
                gl.viewport(0, 0, width, height);
            }
        };
        const render = (now) => {
            pointer.x += (pointer.tx - pointer.x) * 0.06;
            pointer.y += (pointer.ty - pointer.y) * 0.06;
            gl.uniform2f(uniform.r, canvas.width, canvas.height);
            gl.uniform1f(uniform.t, seed + now / 1000);
            gl.uniform2f(uniform.m, pointer.x, pointer.y);
            gl.uniform1f(uniform.k, 0.58);
            gl.drawArrays(gl.TRIANGLES, 0, 3);
        };
        const loop = (now) => {
            raf = 0;
            if (lost) return;
            if (now - last >= 33) {
                last = now;
                render(now);
            }
            if (!paused()) raf = requestAnimationFrame(loop);
        };
        const start = () => {
            if (lost) return;
            if (paused()) {
                if (raf) cancelAnimationFrame(raf);
                raf = 0;
                render(performance.now());
                return;
            }
            if (!raf) raf = requestAnimationFrame(loop);
        };
        let resizeFrame = 0;
        window.addEventListener('resize', () => {
            if (resizeFrame) return;
            resizeFrame = requestAnimationFrame(() => { resizeFrame = 0; resize(); render(performance.now()); });
        }, { passive: true });
        if (finePointer.matches) {
            window.addEventListener('pointermove', (event) => {
                pointer.tx = event.clientX / window.innerWidth;
                pointer.ty = 1 - event.clientY / window.innerHeight;
            }, { passive: true });
        }
        canvas.addEventListener('webglcontextlost', (event) => { event.preventDefault(); lost = true; }, false);
        onMotion(start);
        resize();
        render(performance.now());
        canvas.classList.add('is-live');
        start();
    }

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

    /* Command menu: ⌘K, Ctrl K or "/" opens it. It filters the commands and searches the text of
       this page, then can take you to the best match. Arrows move, Enter opens, Esc closes. */
    function commandMenu() {
        const dialog = $('dialog.command');
        const trigger = $('.command-trigger');
        if (!dialog || typeof dialog.showModal !== 'function') {
            if (trigger) trigger.hidden = true;
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
        const key = $('[data-command-key]');
        const apple = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || '');
        if (key) {
            if (finePointer.matches) key.textContent = apple ? '⌘K' : 'Ctrl K';
            else key.hidden = true;
        }
        if (input) input.placeholder = i18n('search', 'Type a command or search');

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
        const open = () => {
            if (dialog.open) return;
            lastFocus = document.activeElement;
            input.value = '';
            filter();
            dialog.showModal();
            input.focus();
        };
        const close = () => { if (dialog.open) dialog.close(); };
        let lastFocus = null;
        let keepFocus = false;
        dialog.addEventListener('close', () => {
            if (!keepFocus && lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus({ preventScroll: true });
            keepFocus = false;
        });
        if (trigger) trigger.addEventListener('click', open);
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
                const label = button.textContent;
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

    /* The glass pill that follows the hovered or current section link. */
    function navGlow() {
        const nav = $('.site-nav');
        const glow = nav && $('.nav-glow', nav);
        if (!glow) return;
        const links = $$('a', nav);
        let hovered = null;
        const place = () => {
            const target = hovered || links.find((link) => link.classList.contains('is-active'));
            if (!target || getComputedStyle(glow).display === 'none') {
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

    /* The name assembles itself, then settles into crisp text with a light sheen. */
    function heroName() {
        const heading = $('.hero-name[data-split]');
        if (!heading || reduceQuery.matches) return;
        // A page opened out of sight (a background tab, a preview renderer) shows the finished name.
        if (document.hidden) {
            $$(':scope > span', heading).forEach((span) => {
                span.classList.add('name-line');
                span.dataset.text = span.textContent.trim();
            });
            heading.classList.add('is-settled');
            return;
        }
        const words = $$(':scope > span', heading).map((span) => span.textContent.trim()).filter(Boolean);
        if (!words.length) return;
        const original = Array.from(heading.childNodes, (node) => node.cloneNode(true));
        const label = document.createElement('span');
        label.className = 'sr-only';
        label.textContent = words.join(' ');
        const segmenter = !rtl && window.Intl && Intl.Segmenter ? new Intl.Segmenter(lang, { granularity: 'grapheme' }) : null;
        let index = 0;
        const lines = words.map((word) => {
            const line = document.createElement('span');
            line.className = 'name-line';
            line.setAttribute('aria-hidden', 'true');
            line.dataset.text = word;
            const parts = rtl ? [word] : segmenter ? Array.from(segmenter.segment(word), (part) => part.segment) : Array.from(word);
            parts.forEach((part) => {
                const char = document.createElement('span');
                char.className = 'ch';
                char.textContent = part;
                char.style.setProperty('--i', String(index));
                index += 1;
                line.append(char);
            });
            return line;
        });
        heading.replaceChildren(label, ...lines);
        heading.classList.add('is-split');
        let settled = false;
        // Once assembled, restore the original markup so the heading reads exactly as authored.
        const settle = () => {
            if (settled) return;
            settled = true;
            heading.replaceChildren(...original);
            $$(':scope > span', heading).forEach((span) => {
                span.classList.add('name-line');
                span.dataset.text = span.textContent.trim();
            });
            heading.classList.remove('is-split');
            heading.classList.add('is-settled');
        };
        const lastChar = lines[lines.length - 1].lastElementChild;
        if (lastChar) lastChar.addEventListener('animationend', settle, { once: true });
        reduceQuery.addEventListener('change', () => { if (reduceQuery.matches) settle(); });
        onMotion((detail) => { if (detail.user) settle(); });
        const safety = () => {
            if (settled) return;
            if (document.hidden || !root.classList.contains('is-loaded')) {
                window.setTimeout(safety, 800);
                return;
            }
            window.setTimeout(settle, 3600);
        };
        window.setTimeout(safety, 400);
    }

    /* Holographic ID card: tilt and foil follow the pointer. */
    function holoCard() {
        const visual = $('.hero-visual');
        const card = visual && $('.holo-card', visual);
        const inner = card && $('.holo-inner', card);
        if (!inner || !finePointer.matches) return;
        let frame = 0;
        let x = 0.5;
        let y = 0.5;
        const apply = () => {
            frame = 0;
            card.style.setProperty('--ry', `${((x - 0.5) * 16).toFixed(2)}deg`);
            card.style.setProperty('--rx', `${((0.5 - y) * 12).toFixed(2)}deg`);
            inner.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`);
            inner.style.setProperty('--my', `${(y * 100).toFixed(1)}%`);
        };
        visual.addEventListener('pointermove', (event) => {
            if (paused()) return;
            const rect = card.getBoundingClientRect();
            x = Math.min(1.3, Math.max(-0.3, (event.clientX - rect.left) / rect.width));
            y = Math.min(1.3, Math.max(-0.3, (event.clientY - rect.top) / rect.height));
            card.classList.add('is-tilting');
            if (!frame) frame = requestAnimationFrame(apply);
        });
        visual.addEventListener('pointerleave', () => {
            card.classList.remove('is-tilting');
            card.style.setProperty('--rx', '0deg');
            card.style.setProperty('--ry', '0deg');
        });
    }

    /* Capability nodes drift around the card; light beams keep them wired to it. */
    function beams() {
        const visual = $('.hero-visual');
        const group = visual && $('.beam-paths', visual);
        const card = visual && $('.holo-card', visual);
        const nodes = visual ? $$('.orbit-node', visual) : [];
        if (!group || !card || !nodes.length) return;
        const ns = 'http://www.w3.org/2000/svg';
        const items = nodes.map((node, index) => {
            const beam = document.createElementNS(ns, 'path');
            beam.setAttribute('class', 'beam');
            const pulse = document.createElementNS(ns, 'path');
            pulse.setAttribute('class', 'beam-pulse');
            pulse.setAttribute('pathLength', '100');
            group.append(beam, pulse);
            return { node, beam, pulse, phase: index * 1.9, ax: 6 + (index % 2) * 3, ay: 8 + ((index + 1) % 2) * 3, speed: 0.00042 + index * 0.00008, fx: 0, fy: 0, box: null };
        });
        let cardBox = null;
        let raf = 0;
        let visible = true;
        const measure = () => {
            cardBox = { x: card.offsetLeft, y: card.offsetTop, w: card.offsetWidth, h: card.offsetHeight };
            items.forEach((item) => {
                const shown = item.node.offsetParent !== null && item.node.offsetWidth > 0;
                item.box = shown ? { x: item.node.offsetLeft, y: item.node.offsetTop, w: item.node.offsetWidth, h: item.node.offsetHeight } : null;
            });
        };
        const draw = () => {
            const centre = cardBox.x + cardBox.w / 2;
            items.forEach((item) => {
                if (!item.box) {
                    item.beam.setAttribute('d', '');
                    item.pulse.setAttribute('d', '');
                    return;
                }
                const sx = item.box.x + item.box.w / 2 + item.fx;
                const sy = item.box.y + item.box.h / 2 + item.fy;
                const top = cardBox.y;
                const bottom = cardBox.y + cardBox.h;
                const outside = sx < cardBox.x - 24 || sx > cardBox.x + cardBox.w + 24;
                let path = '';
                if (outside) {
                    const left = sx < centre;
                    const ex = left ? cardBox.x + 6 : cardBox.x + cardBox.w - 6;
                    const ey = Math.min(Math.max(sy, top + 48), bottom - 48);
                    const bend = (ex - sx) * 0.55;
                    path = `M${sx.toFixed(1)} ${sy.toFixed(1)}C${(sx + bend).toFixed(1)} ${sy.toFixed(1)} ${(ex - bend).toFixed(1)} ${ey.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`;
                } else if (sy < top - 12 || sy > bottom + 12) {
                    const above = sy < top;
                    const ex = Math.min(Math.max(sx, cardBox.x + 36), cardBox.x + cardBox.w - 36);
                    const ey = above ? top + 6 : bottom - 6;
                    const bend = (ey - sy) * 0.55;
                    path = `M${sx.toFixed(1)} ${sy.toFixed(1)}C${sx.toFixed(1)} ${(sy + bend).toFixed(1)} ${ex.toFixed(1)} ${(ey - bend).toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`;
                }
                item.beam.setAttribute('d', path);
                item.pulse.setAttribute('d', path);
            });
        };
        let last = 0;
        const loop = (now) => {
            raf = 0;
            if (!cardBox) measure();
            const moving = !paused() && visible;
            if (moving && now - last < 32) {
                raf = requestAnimationFrame(loop);
                return;
            }
            last = now;
            if (moving) {
                items.forEach((item) => {
                    const t = now * item.speed + item.phase;
                    item.fx = Math.sin(t) * item.ax;
                    item.fy = Math.cos(t * 1.3) * item.ay;
                    item.node.style.setProperty('--fx', `${item.fx.toFixed(2)}px`);
                    item.node.style.setProperty('--fy', `${item.fy.toFixed(2)}px`);
                });
            }
            draw();
            if (moving) raf = requestAnimationFrame(loop);
        };
        const kick = () => { if (!raf) raf = requestAnimationFrame(loop); };
        if ('ResizeObserver' in window) {
            const observer = new ResizeObserver(() => { measure(); kick(); });
            observer.observe(visual);
            nodes.forEach((node) => observer.observe(node));
        } else {
            window.addEventListener('resize', () => { measure(); kick(); }, { passive: true });
        }
        if ('IntersectionObserver' in window) {
            new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; kick(); }).observe(visual);
        }
        onMotion(kick);
        measure();
        kick();
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
        let visible = false;
        const stop = () => { window.clearTimeout(timer); timer = 0; };
        const next = () => {
            timer = 0;
            frame = frame >= steps.length ? 0 : frame + 1;
            show(frame);
            schedule();
        };
        const schedule = () => {
            if (timer || !visible || paused()) return;
            timer = window.setTimeout(next, frame >= steps.length ? 3400 : 1400);
        };
        const sync = () => {
            if (reduceQuery.matches) {
                stop();
                frame = steps.length;
                show(frame);
                return;
            }
            if (!visible || paused()) stop(); else schedule();
        };
        if ('IntersectionObserver' in window) {
            new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; sync(); }, { threshold: 0.35 }).observe(run);
        } else {
            visible = true;
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

    /* A dot grid that brightens around the pointer. */
    function ambientGrid() {
        const grid = $('.ambient-grid');
        if (!grid || !finePointer.matches) return;
        let frame = 0;
        let x = 0;
        let y = 0;
        window.addEventListener('pointermove', (event) => {
            x = event.clientX;
            y = event.clientY;
            if (!frame) {
                frame = requestAnimationFrame(() => {
                    frame = 0;
                    grid.style.setProperty('--gx', `${x}px`);
                    grid.style.setProperty('--gy', `${y}px`);
                });
            }
        }, { passive: true });
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
        $$('.hero-copy, .hero-visual, .ventures, .agent-run, .work-grid, .guide-tile, .contact').forEach((target) => observer.observe(target));
    }

    /* Keep the command-menu motion item in step with the motion toggle. */
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

    [aurora, clock, commandMenu, copyEmail, navGlow, heroName, holoCard, beams, magnetic, agentRun, timeline, ambientGrid, stagger, offscreen, motionCommand].forEach((feature) => {
        try {
            feature();
        } catch (error) {
            if (window.console) console.warn('[a-samadi.com]', feature.name, error);
        }
    });
})();
