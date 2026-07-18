(function () {
  'use strict';

  const STORAGE_KEY = 'bago.manager.interactions';
  const MAX_ENTRIES = 250;

  function clone(value) {
    try {
      return value == null ? null : JSON.parse(JSON.stringify(value));
    } catch {
      return String(value);
    }
  }

  function readLog() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  }

  function writeLog(entries) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
    } catch {}
  }

  function describeElement(el) {
    if (!el || !el.tagName) return null;
    const tag = el.tagName.toLowerCase();
    const descriptor = {
      tag,
      id: el.id || '',
      name: el.name || '',
      type: el.type || '',
      value: 'value' in el ? String(el.value || '') : '',
      checked: !!el.checked,
      text: String(el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
    };
    if (el.multiple && el.selectedOptions) {
      descriptor.selected = Array.from(el.selectedOptions).map((option) => option.value);
    }
    return descriptor;
  }

  function shouldCaptureClick(el) {
    if (!el) return false;
    const tag = el.tagName && el.tagName.toLowerCase();
    if (tag === 'button' || tag === 'a' || tag === 'summary') return true;
    if (el.closest('[data-pm-view], [data-pm-job-action], [data-pm-install-action], [data-session-id], .section-tab')) return true;
    return false;
  }

  function shouldCaptureInput(el) {
    if (!el) return false;
    const tag = el.tagName && el.tagName.toLowerCase();
    if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') return false;
    return !!(el.id || el.name || String(el.className || '').includes('pm-') || String(el.className || '').includes('input-area'));
  }

  function log(event, payload) {
    const entry = {
      ts: new Date().toISOString(),
      source: 'manager',
      event,
      payload: clone(payload),
    };
    const next = [entry].concat(readLog()).slice(0, MAX_ENTRIES);
    writeLog(next);
    window.__bagoInteractionLog = next;
    try {
      window.dispatchEvent(new CustomEvent('bago:interaction', { detail: entry }));
    } catch {}
    try {
      console.debug('[BAGO interaction]', entry);
    } catch {}
    return entry;
  }

  function install() {
    document.addEventListener('click', function (event) {
      const target = event.target && event.target.closest && event.target.closest('button, a, summary, [data-pm-view], [data-pm-job-action], [data-pm-install-action], [data-session-id], .section-tab');
      if (!shouldCaptureClick(target)) return;
      log('click', {
        target: describeElement(target),
        view: document.querySelector('.pm-view.active') && document.querySelector('.pm-view.active').id.replace('pm-view-', ''),
      });
    }, true);

    document.addEventListener('change', function (event) {
      const target = event.target;
      if (!shouldCaptureInput(target)) return;
      log('change', {
        target: describeElement(target),
        view: document.querySelector('.pm-view.active') && document.querySelector('.pm-view.active').id.replace('pm-view-', ''),
      });
    }, true);

    document.addEventListener('submit', function (event) {
      const form = event.target;
      if (!form || !form.querySelector) return;
      log('submit', {
        target: describeElement(form),
        fields: Array.from(form.querySelectorAll('input, textarea, select')).map(describeElement),
      });
    }, true);
  }

  window.__bagoInteractionLogPush = log;
  window.__bagoInteractionLogRead = readLog;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
}());
