/* Decorative projected geometry. No network, tracking or generated claims. */
(() => {
  const canvas = document.querySelector('.orbital-canvas');
  const scene = document.querySelector('.future-art');
  const hero = document.querySelector('.hero');
  if (!canvas || !scene || !hero) return;
  const context = canvas.getContext('2d');
  if (!context) return;
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const toggle = document.querySelector('.motion-toggle');
  let width = 600, height = 600, inView = true, frame = 0, lastTime = 0, phase = .5;
  let pointerX = 0, pointerY = 0, smoothX = 0, smoothY = 0;
  const points = [];
  const count = 300;
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const angle = golden * i;
    points.push({ x: Math.cos(angle) * radius, y, z: Math.sin(angle) * radius });
  }
  const paused = () => preference.matches || toggle?.getAttribute('aria-pressed') === 'true' || document.hidden || !inView;
  const project = (x, y, z, radius, angle) => {
    const a = x * Math.cos(angle) + z * Math.sin(angle);
    const c = z * Math.cos(angle) - x * Math.sin(angle);
    const b = y * Math.cos(.25) - c * Math.sin(.25);
    const depth = c * Math.cos(.25) + y * Math.sin(.25);
    const perspective = 3.8 / (3.8 - depth * .22);
    return { x: width / 2 + a * radius * perspective + smoothX, y: height / 2 + b * radius * perspective + smoothY, z: depth };
  };
  const draw = () => {
    context.clearRect(0, 0, width, height);
    const radius = Math.min(width, height) * .415;
    smoothX += (pointerX - smoothX) * .045;
    smoothY += (pointerY - smoothY) * .045;
    const angle = phase * .13;
    // Longitude and latitude lines make a dimensional globe without WebGL.
    for (let ring = 0; ring < 12; ring++) {
      context.beginPath();
      for (let step = 0; step <= 100; step++) {
        const t = step / 100 * Math.PI * 2;
        const fixed = ring / 12 * Math.PI;
        const p = project(Math.cos(t) * Math.cos(fixed), Math.sin(t), Math.cos(t) * Math.sin(fixed), radius, angle);
        step ? context.lineTo(p.x, p.y) : context.moveTo(p.x, p.y);
      }
      context.strokeStyle = 'rgba(120, 151, 223, .16)'; context.lineWidth = .7; context.stroke();
    }
    for (let ring = 1; ring < 9; ring++) {
      const latitude = ring / 9 * Math.PI;
      context.beginPath();
      for (let step = 0; step <= 100; step++) {
        const t = step / 100 * Math.PI * 2;
        const p = project(Math.sin(latitude) * Math.cos(t), Math.cos(latitude), Math.sin(latitude) * Math.sin(t), radius, angle);
        step ? context.lineTo(p.x, p.y) : context.moveTo(p.x, p.y);
      }
      context.strokeStyle = 'rgba(139, 155, 223, .18)';context.lineWidth = .7;context.stroke();
    }
    const projected = points.map((p, i) => ({ ...project(p.x, p.y, p.z, radius, angle), i })).sort((a, b) => a.z - b.z);
    for (const p of projected) {
      const front = (p.z + 1) / 2;
      const pulse = .65 + .35 * Math.sin(phase * .9 + p.i * .17);
      context.fillStyle = `rgba(${p.i % 5 === 0 ? '137, 124, 215' : '69, 126, 226'}, ${(.12 + front * .48) * pulse})`;
      context.beginPath();context.arc(p.x, p.y, .8 + front * 1.25, 0, Math.PI * 2);context.fill();
    }
    // Three luminous satellites trace different orbital planes.
    for (let i = 0; i < 3; i++) {
      const a = phase * (.17 + i * .045) + i * 2.1;
      const x = Math.cos(a) * 1.07, y = Math.sin(a) * (.4 + i * .2), z = Math.sin(a) * .6;
      const p = project(x, y, z, radius, angle);
      const glow = context.createRadialGradient(p.x, p.y, 1, p.x, p.y, 14);
      glow.addColorStop(0, i === 1 ? '#b7a4fabb' : '#83b1ffcc');glow.addColorStop(1, '#a3c3ff00');
      context.fillStyle = glow;context.beginPath();context.arc(p.x, p.y, 14, 0, Math.PI * 2);context.fill();
      context.fillStyle = '#fff';context.beginPath();context.arc(p.x, p.y, 3.6, 0, Math.PI * 2);context.fill();
      context.fillStyle = i === 1 ? '#9b87d8' : '#4986ed';context.beginPath();context.arc(p.x, p.y, 2.4, 0, Math.PI * 2);context.fill();
    }
  };
  const animate = (time) => {
    frame = 0;
    if (paused()) { lastTime = 0; return; }
    const elapsed = lastTime ? Math.min((time - lastTime) / 1000, .05) : 0;
    lastTime = time;phase += elapsed;draw();frame = requestAnimationFrame(animate);
  };
  const sync = () => {
    if (paused()) { cancelAnimationFrame(frame);frame = 0;lastTime = 0;scene.style.removeProperty('--scene-x');scene.style.removeProperty('--scene-y');draw(); }
    else if (!frame) frame = requestAnimationFrame(animate);
  };
  const resize = () => {
    const bounds = canvas.getBoundingClientRect();
    width = bounds.width; height = bounds.height;
    const ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);canvas.height = Math.round(height * ratio);context.setTransform(ratio, 0, 0, ratio, 0, 0);draw();sync();
  };
  hero.addEventListener('pointermove', event => {
    if (paused() || event.pointerType === 'touch') return;
    const bounds = scene.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, (event.clientX - bounds.left) / bounds.width * 2 - 1));
    const y = Math.max(-1, Math.min(1, (event.clientY - bounds.top) / bounds.height * 2 - 1));
    pointerX = x * 8;pointerY = y * 6;
    scene.style.setProperty('--scene-x', `${-y * 5}deg`);scene.style.setProperty('--scene-y', `${x * 6}deg`);
  }, { passive: true });
  hero.addEventListener('pointerleave', () => { pointerX = pointerY = 0;scene.style.removeProperty('--scene-x');scene.style.removeProperty('--scene-y'); });
  document.addEventListener('visibilitychange', sync);preference.addEventListener('change', sync);window.addEventListener('site:motion', sync);
  if ('IntersectionObserver' in window) new IntersectionObserver(entries => { inView = entries[0].isIntersecting;sync(); }, { rootMargin: '50px' }).observe(hero);
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(scene);else window.addEventListener('resize', resize, { passive: true });
  resize();
})();
