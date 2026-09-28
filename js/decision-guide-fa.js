'use strict';
(() => {
  const form = document.getElementById('decision-form');
  const content = document.getElementById('brief-content');
  const status = document.getElementById('status');
  const keys = ['user', 'decision', 'action', 'evidence', 'availability', 'stakes', 'review', 'baseline', 'success'];
  const examples = {
    property: { user: 'پژوهشگر املاک', decision: 'پیش از آنکه سرمایه‌گذار وقت بیشتری بگذارد، کدام ملک‌ها ارزش بررسی دقیق‌تر دارند؟', action: 'گزینه‌های مناسب را فهرست کنید و اطلاعات تکمیلی یا بازدید دستی بخواهید.', evidence: 'تصاویر دارای تاریخ، ویژگی‌های مرتبط ملک و منشأ داده‌ها. مشخص کنید تصاویر چه چیزهایی را اثبات نمی‌کنند.', availability: 'partial', stakes: 'medium', review: 'always', baseline: 'پژوهشگر هر آگهی را بررسی و فهرست گزینه‌ها را دستی تهیه می‌کند.', success: 'زمان پژوهش کاهش یابد، گزینه‌های مفید حفظ شوند، کمبود شواهد روشن باشد و زمان بازبینی نیز محاسبه شود.' },
    support: { user: 'مسئول پشتیبانی مشتری', decision: 'کدام درخواست‌های ورودی پیش از نوبت بعدی دسته‌بندی به رسیدگی تخصصی نیاز دارند؟', action: 'درخواست بازبینی‌شده را همراه با اطلاعات پشتیبان به تیم مناسب ارجاع دهید.', evidence: 'متن درخواست، مستندات مرتبط محصول و نمونه‌های تأییدشده ارجاع‌های قبلی، با مجوز استفاده از آن‌ها.', availability: 'unknown', stakes: 'low', review: 'exceptions', baseline: 'مسئول پشتیبانی صف را می‌خواند و هر درخواست را دستی ارجاع می‌دهد.', success: 'زحمت ارجاع کم شود، بدون افزایش درخواست‌های فوری ازدست‌رفته یا زمان اصلاح ارجاع‌ها.' }
  };
  let briefText = '';
  let dirty = false;
  function values() { return Object.fromEntries(keys.map(key => [key, form.elements[key].value.trim()])); }
  function section(title, body, ordered = false) {
    const wrap = document.createElement('section'); wrap.className = 'brief-section';
    const h = document.createElement('h3'); h.textContent = title; wrap.append(h);
    if (ordered) { const list = document.createElement('ol'); body.forEach(text => { const li = document.createElement('li'); li.textContent = text; list.append(li); }); wrap.append(list); }
    else { const p = document.createElement('p'); p.textContent = body; wrap.append(p); }
    content.append(wrap);
    return title.toUpperCase() + '\n' + (ordered ? body.map((s, i) => `${i + 1}. ${s}`).join('\n') : body);
  }
  function build(message) {
    const v = values();
    content.replaceChildren();
    const blocker = v.availability === 'unknown' ? 'پیش از آزمایش مدل، شواهد را بررسی کنید. دسترسی، مجوز استفاده، به‌روز بودن و پوشش را تأیید کنید و موارد نامعلوم را بنویسید.' : v.availability === 'partial' ? 'شکاف‌ها را آشکار کنید. منابع مفقود را مشخص کنید و تعیین کنید ابزار چه زمانی باید اطلاعات بخواهد یا تصمیم را به انسان برگرداند.' : 'شواهد را با موارد واقعی بسنجید. موجودبودن به معنای دقت یا نمایندگی مناسب نیست؛ منشأ و موارد دشوار را بررسی کنید.';
    const review = v.stakes === 'high' ? 'آزمایش نخست را آفلاین نگه دارید و از فرد واجد صلاحیت بخواهید همه نتایج را بازبینی کند. پیش از استفاده عملی، خطاهای جدی و شرایط ارجاع را مستند کنید.' : v.review === 'none' ? 'مرحله بازبینی را به آزمایش نخست اضافه کنید. پیش از آنکه خروجی به اقدام منجر شود، یک نفر باید شواهد و خطاها را بررسی کند.' : v.review === 'exceptions' ? 'در آزمایش نخست همه نتایج، حتی موارد علامت‌گذاری‌نشده، را بازبینی کنید. پیش از اتکا به قواعد استثنا، بررسی کنید آیا خطایی از دست می‌رود.' : 'بازبین را در آزمایش نگه دارید. اصلاحات و زمان بازبینی هر نتیجه را در کنار خروجی مدل ثبت کنید.';
    const parts = [section('۰۱ / تصمیم', `${v.user}\n\n${v.decision}`), section('اقدام بعدی', v.action), section('۰۲ / شواهد', v.evidence), section('ابتدا حل کنید', blocker + '\n\n' + review), section('۰۳ / کوچک‌ترین آزمایش مفید', [
      `مجموعه‌ای کوچک با دامنه روشن از موارد این تصمیم انتخاب کنید. موارد عادی، شواهد ناقص و خطاهای محتمل را بگنجانید. آزمایش کوچک را اثبات قابلیت اعتماد گسترده ندانید.`,
      `روش مبنا را مشخص کنید: ${v.baseline} زمان، نتایج و زحمت اصلاح را ثبت کنید.`,
      `برای همان موارد، دستی یا با نمونه‌ای ساده، پیشنهادهای مستند به شواهد آماده کنید. ${review}`,
      `با معیار خود مقایسه کنید: ${v.success} پیش از آزمایش، شرایط قابل‌اندازه‌گیری موفقیت و توقف را تعیین کنید و هزینه اجرا و بازبینی را بگنجانید.`
    ], true), section('فقط زمانی ادامه دهید که', 'شواهد از اقدام موردنظر پشتیبانی کنند، برای خطاها مسیر جایگزین روشن باشد و کل فرایند از روش فعلی بهتر عمل کند. در غیر این صورت تصمیم را محدودتر یا ورودی‌ها را بازنگری کنید.')];
    briefText = 'پیش از ساخت هوش مصنوعی\nبرگه تصمیم · احمدرضا صمدی\n\n' + parts.join('\n\n') + '\n\nکمکی ساختاریافته برای فکرکردن؛ نه ارزیابی اعتبارسنجی‌شده.\nhttps://a-samadi.com/fa/tools/before-you-build-ai.html\n';
    dirty = false; status.textContent = message;
    document.getElementById('download').disabled = false; document.getElementById('print').disabled = false;
  }
  function load(name) {
    form.reset(); keys.forEach(key => { form.elements[key].setCustomValidity(''); if (examples[name]) form.elements[key].value = examples[name][key]; });
    document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.example === name)));
    if (name === 'blank') { content.replaceChildren(); briefText = ''; dirty = true; status.textContent = 'برگه را کامل کنید، سپس برگه تصمیم را بسازید.'; document.getElementById('download').disabled = true; document.getElementById('print').disabled = true; form.elements.user.focus(); }
    else build('نمونه فرضی بارگذاری شد. جزئیات را تغییر دهید و برگه را دوباره بسازید.');
  }
  form.addEventListener('input', () => { dirty = true; status.textContent = 'ورودی‌ها تغییر کرده‌اند. برای اعمال آن‌ها برگه را دوباره بسازید.'; document.getElementById('download').disabled = true; document.getElementById('print').disabled = true; document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed', 'false')); });
  form.addEventListener('submit', event => { event.preventDefault(); const empty = keys.find(key => !form.elements[key].value.trim()); if (empty) { form.elements[empty].setCustomValidity('لطفاً جزئیات مشخصی وارد کنید.'); form.elements[empty].reportValidity(); form.elements[empty].addEventListener('input', () => form.elements[empty].setCustomValidity(''), { once: true }); return; } build('برگه به‌روز شد و آماده دریافت یا چاپ است.'); document.getElementById('brief-heading').focus(); });
  document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => load(button.dataset.example)));
  document.getElementById('download').addEventListener('click', () => { if (dirty || !briefText) return; const url = URL.createObjectURL(new Blob([briefText], { type: 'text/plain;charset=utf-8' })); const link = document.createElement('a'); link.href = url; link.download = 'decision-brief-ahmadreza-samadi-fa.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status.textContent = 'برگه به‌صورت فایل متنی دریافت شد.'; });
  document.getElementById('print').addEventListener('click', () => { if (!dirty) window.print(); });
  document.getElementById('interactive').hidden = false;
  load('property');
})();
