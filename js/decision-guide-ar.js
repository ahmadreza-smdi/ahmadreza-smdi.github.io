'use strict';
(() => {
  const form = document.getElementById('decision-form');
  const content = document.getElementById('brief-content');
  const status = document.getElementById('status');
  const keys = ['user', 'decision', 'action', 'evidence', 'availability', 'stakes', 'review', 'baseline', 'success'];
  const examples = {
    property: { user: 'باحث عقاري', decision: 'ما العقارات التي تستحق تحقيقاً أعمق قبل أن يخصص المستثمر مزيداً من الوقت؟', action: 'أعد قائمة مختصرة واطلب المعلومات الناقصة أو معاينة يدوية.', evidence: 'صور مؤرخة للعقار وخصائصه ذات الصلة ومصادر البيانات. دوّن ما لا تستطيع الصور إثباته.', availability: 'partial', stakes: 'medium', review: 'always', baseline: 'يفحص الباحث كل إعلان ويعد قائمة مختصرة يدوياً.', success: 'تقليل وقت البحث مع الاحتفاظ بالخيارات المفيدة، وإظهار الأدلة الناقصة واحتساب جهد المراجعة.' },
    support: { user: 'مسؤول دعم العملاء', decision: 'ما الطلبات الواردة التي تحتاج إلى اهتمام متخصص قبل جولة الفرز التالية؟', action: 'وجّه الطلب الذي تمت مراجعته إلى الفريق المناسب مع سياقه الداعم.', evidence: 'نص الطلب ووثائق المنتج ذات الصلة وأمثلة مؤكدة لقرارات توجيه سابقة، مع إذن استخدامها.', availability: 'unknown', stakes: 'low', review: 'exceptions', baseline: 'يقرأ مسؤول الدعم قائمة الانتظار ويوجه كل طلب يدوياً.', success: 'تقليل جهد التوجيه دون زيادة الطلبات العاجلة الفائتة أو الوقت المستغرق في تصحيح الإسناد.' }
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
    const blocker = v.availability === 'unknown' ? 'افحص الأدلة قبل اختبار النموذج. تحقق من الوصول والاستخدام المسموح والحداثة والتغطية، ودوّن ما لا يزال مجهولاً.' : v.availability === 'partial' ? 'أظهر الفجوات. حدد المصادر الناقصة ومتى يجب أن تطلب الأداة معلومات إضافية أو تعيد القرار إلى شخص.' : 'اختبر الأدلة على حالات فعلية. إتاحتها لا تثبت دقتها أو تمثيلها للحالات؛ افحص مصادرها والحالات الصعبة.';
    const review = v.stakes === 'high' ? 'أبقِ التجربة الأولى خارج التشغيل الفعلي، مع مراجعة شخص مؤهل لكل نتيجة. وثّق حالات الفشل الجسيم وشروط التصعيد قبل التفكير في الاستخدام الفعلي.' : v.review === 'none' ? 'أضف خطوة مراجعة إلى التجربة الأولى. يجب أن يفحص شخص الأدلة والأخطاء قبل أن تؤدي المخرجات إلى إجراء.' : v.review === 'exceptions' ? 'راجع كل نتيجة في التجربة الأولى، بما فيها الحالات غير المعلّمة. تحقق مما إذا كانت قواعد الاستثناء تفوّت أخطاء قبل الاعتماد عليها.' : 'أبقِ المراجع ضمن الاختبار. سجل التصحيحات والوقت اللازم لمراجعة كل نتيجة إلى جانب مخرجات النموذج.';
    const parts = [section('٠١ / القرار', `${v.user}\n\n${v.decision}`), section('الإجراء التالي', v.action), section('٠٢ / الأدلة', v.evidence), section('عالج أولاً', blocker + '\n\n' + review), section('٠٣ / أصغر تجربة مفيدة', [
      `اختر مجموعة صغيرة ومحددة النطاق من الحالات لهذا القرار. ضمّن حالات معتادة وأدلة ناقصة وإخفاقات محتملة. لا تعتبر تجربة صغيرة دليلاً على موثوقية واسعة.`,
      `حدد خط الأساس: ${v.baseline} سجل الوقت والنتائج وجهد التصحيح.`,
      `جهز اقتراحات مدعومة بالأدلة للحالات نفسها، يدوياً أو بنموذج أولي بسيط. ${review}`,
      `قارن بمعيارك: ${v.success} حدد شروط نجاح وتوقف قابلة للقياس قبل الاختبار، مع احتساب تكاليف التنفيذ والمراجعة.`
    ], true), section('تابع فقط عندما', 'تدعم الأدلة الإجراء المقصود، ويكون للفشل بديل واضح، ويتفوق سير العمل الكامل على الطريقة الحالية. وإلا فضيّق نطاق القرار أو أعد النظر في المدخلات.')];
    briefText = 'قبل بناء الذكاء الاصطناعي\nموجز قرار · أحمدرضا صمدي\n\n' + parts.join('\n\n') + '\n\nأداة منظمة للتفكير؛ وليست تقييماً جرى التحقق من صلاحيته.\nhttps://a-samadi.com/ar/tools/before-you-build-ai.html\n';
    dirty = false; status.textContent = message;
    document.getElementById('download').disabled = false; document.getElementById('print').disabled = false;
  }
  function load(name) {
    form.reset(); keys.forEach(key => { form.elements[key].setCustomValidity(''); if (examples[name]) form.elements[key].value = examples[name][key]; });
    document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.example === name)));
    if (name === 'blank') { content.replaceChildren(); briefText = ''; dirty = true; status.textContent = 'أكمل الورقة ثم أنشئ الموجز.'; document.getElementById('download').disabled = true; document.getElementById('print').disabled = true; form.elements.user.focus(); }
    else build('تم تحميل مثال توضيحي. عدّل أي تفصيل ثم أعد إنشاء الموجز.');
  }
  form.addEventListener('input', () => { dirty = true; status.textContent = 'تغيرت مدخلاتك. أعد إنشاء الموجز لتضمينها.'; document.getElementById('download').disabled = true; document.getElementById('print').disabled = true; document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed', 'false')); });
  form.addEventListener('submit', event => { event.preventDefault(); const empty = keys.find(key => !form.elements[key].value.trim()); if (empty) { form.elements[empty].setCustomValidity('يرجى إضافة تفصيل محدد.'); form.elements[empty].reportValidity(); form.elements[empty].addEventListener('input', () => form.elements[empty].setCustomValidity(''), { once: true }); return; } build('تم تحديث الموجز. أصبح جاهزاً للتصدير أو الطباعة.'); document.getElementById('brief-heading').focus(); });
  document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => load(button.dataset.example)));
  document.getElementById('download').addEventListener('click', () => { if (dirty || !briefText) return; const url = URL.createObjectURL(new Blob([briefText], { type: 'text/plain;charset=utf-8' })); const link = document.createElement('a'); link.href = url; link.download = 'decision-brief-ahmadreza-samadi-ar.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status.textContent = 'تم تصدير الموجز كملف نصي.'; });
  document.getElementById('print').addEventListener('click', () => { if (!dirty) window.print(); });
  document.getElementById('interactive').hidden = false;
  load('property');
})();
