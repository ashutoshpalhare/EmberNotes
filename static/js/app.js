(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const typing = (el) => el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);

  const stack = $('#toasts');
  const dismiss = (el) => { el.classList.add('leaving'); setTimeout(() => el.remove(), 220); };
  function toast(text, kind = 'info') {
    const el = document.createElement('div');
    el.className = `toast toast-${kind}`;
    el.textContent = text;
    stack.append(el);
    setTimeout(() => dismiss(el), 5000);
  }
  $$('.toast').forEach((el) => {
    setTimeout(() => dismiss(el), 5000);
    $('.toast-x', el)?.addEventListener('click', () => dismiss(el));
  });

  const dlg = $('#confirm-dialog');
  const ask = (message, label) => new Promise((resolve) => {
    $('#confirm-msg').textContent = message;
    $('#confirm-ok').textContent = label || 'Confirm';
    dlg.returnValue = '';
    dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'), { once: true });
    dlg.showModal();
  });

  const setDrawer = (open) => document.body.classList.toggle('drawer-open', open);
  $$('[data-drawer-open]').forEach((b) => b.addEventListener('click', () => setDrawer(true)));
  $$('[data-drawer-close]').forEach((b) => b.addEventListener('click', () => setDrawer(false)));
  $('[data-autosubmit]')?.addEventListener('change', (e) => e.target.form.requestSubmit());

  document.addEventListener('submit', async (e) => {
    const f = e.target;
    if (!(f instanceof HTMLFormElement) || !(f.dataset.confirm || f.hasAttribute('data-flush'))) return;
    e.preventDefault();
    if (f.dataset.confirm && !(await ask(f.dataset.confirm, f.dataset.confirmLabel))) return;
    if (f.hasAttribute('data-flush') && window.EmberEditor && !(await window.EmberEditor.flush())) {
      toast('Fix the save problem before continuing.', 'error');
      return;
    }
    f.submit();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') setDrawer(false);
    if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === '/' && $('#search-input')) { e.preventDefault(); $('#search-input').focus(); }
    if (e.key === 'n') $('#new-note-form')?.requestSubmit();
  });

  const form = $('#note-form');
  if (!form) return;
  const url = form.dataset.autosaveUrl;
  const f = form.elements;
  const wc = $('#word-count');
  const grow = () => { f.body.style.height = 'auto'; f.body.style.height = f.body.scrollHeight + 'px'; };
  const words = () => { const n = f.body.value.trim().split(/\s+/).filter(Boolean).length; wc.textContent = `${n} word${n === 1 ? '' : 's'}`; };
  grow();
  const previewButton = $('[data-preview-toggle]');
  const previewPane = $('#markdown-preview');
  if (previewButton && previewPane && form.dataset.previewUrl) {
    let showingPreview = false;
    previewButton.addEventListener('click', async () => {
      if (showingPreview) {
        previewPane.hidden = true;
        f.body.hidden = false;
        previewButton.textContent = 'Preview';
        previewButton.setAttribute('aria-pressed', 'false');
        showingPreview = false;
        grow();
        return;
      }
      previewButton.disabled = true;
      previewButton.textContent = 'Loading…';
      try {
        const response = await fetch(form.dataset.previewUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': f.csrfmiddlewaretoken.value},
          body: JSON.stringify({body: f.body.value})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Preview unavailable');
        previewPane.innerHTML = data.html;
        f.body.hidden = true;
        previewPane.hidden = false;
        previewButton.textContent = 'Edit';
        previewButton.setAttribute('aria-pressed', 'true');
        showingPreview = true;
      } catch (error) {
        toast(error.message || 'Preview unavailable.', 'error');
        previewButton.textContent = 'Preview';
      } finally { previewButton.disabled = false; }
    });
  }
  if (!url) return;

  const pill = $('#save-status'), pillText = $('#save-status-text');
  let timer = null, inflight = null, dirty = false, failed = false;
  const status = (state, text) => { pill.dataset.state = state; pillText.textContent = text; };
  const csrf = () => f.csrfmiddlewaretoken.value;

  async function save() {
    clearTimeout(timer);
    while (inflight) await inflight;
    if (!dirty && !failed) return true;
    dirty = false;
    status('saving', 'Saving…');
    const body = JSON.stringify({ title: f.title.value, body: f.body.value, tags: f.tags.value });
    inflight = (async () => {
      try {
        const r = await fetch(url, { method: 'POST', credentials: 'same-origin', body,
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() } });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || 'Server error');
        if (failed) toast('Back online. Changes saved.', 'success');
        failed = false;
        status(dirty ? 'dirty' : 'saved', dirty ? 'Unsaved changes' : 'All changes saved');
      } catch (err) {
        if (!failed) toast(`Couldn't save: ${err.message}. We'll keep your text and retry.`, 'error');
        failed = true; dirty = true;
        status('error', "Couldn't save. Click to retry");
      } finally { inflight = null; }
    })();
    await inflight;
    return !failed;
  }
  window.EmberEditor = { flush: save };

  const queue = () => { dirty = true; status('dirty', 'Unsaved changes'); clearTimeout(timer); timer = setTimeout(save, 900); };
  [f.title, f.body, f.tags].forEach((el) => el.addEventListener('input', () => { if (el === f.body) { grow(); words(); } queue(); }));
  pill.addEventListener('click', () => { if (failed) save(); });
  window.addEventListener('online', () => { if (failed) save(); });
  window.addEventListener('beforeunload', (e) => { if (dirty || failed || inflight) { e.preventDefault(); e.returnValue = ''; } });

  const manualSave = async () => { const ok = await save(); if (ok) toast('Note saved.', 'success'); };
  form.addEventListener('submit', (e) => { e.preventDefault(); manualSave(); });
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); manualSave(); }
  });

  $$('[data-add-tag]').forEach((b) => b.addEventListener('click', () => {
    const have = f.tags.value.split(',').map((t) => t.trim().toLowerCase()).filter(Boolean);
    if (!have.includes(b.dataset.addTag)) { f.tags.value = [...have, b.dataset.addTag].join(', '); queue(); }
  }));
})();
