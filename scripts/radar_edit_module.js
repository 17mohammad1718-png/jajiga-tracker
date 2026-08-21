/* Radar manual edit module — occupancy status + price overrides (baked into competitor-radar.html) */
(function () {
  var KEY = 'radar_edits_v1';
  var EDITS = {};
  try { EDITS = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { EDITS = {}; }

  /* ---------- CSS ---------- */
  var style = document.createElement('style');
  style.textContent =
    '.edit-btn.active{background:linear-gradient(135deg,#f59e0b,#b45309)!important;box-shadow:0 4px 14px rgba(245,158,11,.35)!important;}' +
    'body.edit-mode td.c{cursor:pointer;}' +
    'body.edit-mode td.c:hover{outline:2px solid #38bdf8;outline-offset:-2px;}' +
    '.cal td.c{position:relative;}' +
    '.cal td.c.edited::after{content:"";position:absolute;top:2px;left:2px;width:6px;height:6px;border-radius:50%;background:#fbbf24;box-shadow:0 0 4px rgba(251,191,36,.8);}' +
    '.edit-pop{position:fixed;z-index:70;background:#111f35;border:1px solid #2d4668;border-radius:12px;box-shadow:0 14px 44px rgba(0,0,0,.55);padding:12px;width:244px;font-size:12px;}' +
    '.edit-pop-title b{display:block;color:#f1f5f9;font-size:12.5px;margin-bottom:2px;}' +
    '.edit-pop-title span{color:#64748b;font-size:11px;}' +
    '.edit-pop-status{display:flex;gap:6px;margin:10px 0 8px;}' +
    '.edit-pop-status button{flex:1;background:#0d1a2e;color:#cbd5e1;border:1px solid #2d4668;border-radius:8px;padding:6px 2px;font-family:inherit;font-size:11.5px;cursor:pointer;}' +
    '.edit-pop-status button.sel{background:linear-gradient(135deg,#0d9488,#0f766e);color:#fff;border-color:#0f766e;font-weight:600;}' +
    '.edit-pop-price label{display:block;color:#94a3b8;font-size:11px;margin-bottom:4px;}' +
    '.edit-pop-price input{width:100%;box-sizing:border-box;background:#0d1a2e;color:#e2e8f0;border:1px solid #2d4668;border-radius:8px;padding:7px 10px;font-family:Consolas,monospace;font-size:12.5px;direction:ltr;text-align:left;}' +
    '.edit-pop-actions{display:flex;gap:6px;margin-top:10px;}' +
    '.edit-pop-actions button{flex:1;background:#0d1a2e;color:#cbd5e1;border:1px solid #2d4668;border-radius:8px;padding:7px 2px;font-family:inherit;font-size:12px;cursor:pointer;}' +
    '.edit-pop-actions .ep-save{background:linear-gradient(135deg,#0d9488,#0f766e);color:#fff;border-color:#0f766e;font-weight:600;}' +
    '#editMgr{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0 14px;}' +
    '.edit-count{color:#94a3b8;font-size:11.5px;margin-right:auto;}' +
    '#editMgr button{background:#111f35;color:#cbd5e1;border:1px solid #1e3a5f;border-radius:8px;padding:6px 12px;font-family:inherit;font-size:11.5px;cursor:pointer;transition:all .15s;}' +
    '#editMgr button:hover{border-color:#38bdf8;color:#fff;}';
  document.head.appendChild(style);

  /* ---------- header button ---------- */
  var btn = document.createElement('button');
  btn.id = 'editModeBtn';
  btn.className = 'export-btn';
  btn.textContent = '✏️ ویرایش';
  btn.title = 'فعال/غیرفعال کردن حالت ویرایش سلول‌ها (وضعیت پر بودن و قیمت)';
  var exp = document.getElementById('exportBtn');
  if (exp) exp.parentNode.insertBefore(btn, exp);

  var on = false;
  function setMode(v) {
    on = v;
    document.body.classList.toggle('edit-mode', v);
    btn.classList.toggle('active', v);
    btn.textContent = v ? '✔️ پایان ویرایش' : '✏️ ویرایش';
    if (!v) closePop();
  }
  btn.onclick = function () { setMode(!on); };

  /* ---------- helpers ---------- */
  var FA_D = { '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9' };
  function faToEn(s) { return String(s).replace(/[۰-۹٠-٩]/g, function (d) { return FA_D[d] || d; }); }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(EDITS)); } catch (e) {} }
  function keyOf(rid, d) { return rid + '|' + d; }

  /* ---------- RE API (consumed by revenue module) ---------- */
  window.RE = {
    get: function (rid, d) {
      var e = EDITS[keyOf(rid, d)];
      if (!e) return null;
      return { s: e.s || null, p: (e.p === undefined || e.p === null || e.p === '') ? null : Number(e.p) };
    },
    count: function () { return Object.keys(EDITS).length; }
  };

  /* ---------- apply edits to cells ---------- */
  var STATUS_CLASSES = ['booked', 'free', 'blocked', 'half', 'peak', 'weekend', 'past', 'nodata', 'notracked'];
  function applyToCell(td) {
    var rid = td.getAttribute('data-r'), d = td.getAttribute('data-d');
    if (!rid || !d) return;
    var e = EDITS[keyOf(rid, d)];
    if (!e) { td.classList.remove('edited'); return; }
    if (e.s) {
      STATUS_CLASSES.forEach(function (c) { td.classList.remove(c); });
      td.classList.add(e.s);
    }
    var pr = td.querySelector('.pr');
    if (pr && e.p !== undefined && e.p !== null && e.p !== '') {
      pr.textContent = Number(e.p).toLocaleString('en-US');
      pr.classList.add('disc');
    }
    td.classList.add('edited');
    var t = td.getAttribute('title') || '';
    if (t.indexOf('✏️ ویرایش') === -1) td.setAttribute('title', t + ' · ✏️ ویرایش دستی');
  }
  function applyAll() {
    var cells = document.querySelectorAll('td.c[data-r][data-d]');
    for (var i = 0; i < cells.length; i++) applyToCell(cells[i]);
  }

  /* ---------- popover ---------- */
  var pop = null;
  function closePop() { if (pop) { pop.remove(); pop = null; } }
  function openPop(td) {
    closePop();
    var rid = td.getAttribute('data-r'), d = td.getAttribute('data-d');
    var e = EDITS[keyOf(rid, d)] || {};
    var rowTd = td.parentNode.querySelector('.rname');
    var title = rowTd ? rowTd.textContent.trim().replace(/\s+/g, ' ').slice(0, 60) : rid;
    var dateLabel = (td.getAttribute('title') || '').split(' · ')[0] || d;
    var curPrice = (e.p !== undefined && e.p !== null && e.p !== '') ? e.p
      : (td.querySelector('.pr') ? td.querySelector('.pr').textContent.replace(/[^0-9]/g, '') : '');
    var selStatus = e.s || null;

    pop = document.createElement('div');
    pop.className = 'edit-pop';
    pop.innerHTML =
      "<div class='edit-pop-title'><b>" + title + "</b><span>" + dateLabel + "</span></div>" +
      "<div class='edit-pop-status'>" +
      "<button data-s='free'" + (selStatus === 'free' ? " class='sel'" : '') + ">خالی</button>" +
      "<button data-s='booked'" + (selStatus === 'booked' ? " class='sel'" : '') + ">پر</button>" +
      "<button data-s='blocked'" + (selStatus === 'blocked' ? " class='sel'" : '') + ">بسته میزبان</button>" +
      "</div>" +
      "<div class='edit-pop-price'><label>قیمت (تومان)</label><input type='text' inputmode='numeric' value='" + curPrice + "'></div>" +
      "<div class='edit-pop-actions'>" +
      "<button class='ep-save'>ذخیره</button>" +
      "<button class='ep-default'>پیش‌فرض</button>" +
      "<button class='ep-cancel'>لغو</button>" +
      "</div>";
    document.body.appendChild(pop);
    var r = td.getBoundingClientRect();
    var vw = window.innerWidth || document.documentElement.clientWidth;
    var left = r.left, top = r.bottom + 4;
    if (left + 244 > vw - 8) left = Math.max(8, vw - 244 - 8);
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';

    var priceInput = pop.querySelector('input');
    var sBtns = pop.querySelectorAll('.edit-pop-status button');
    for (var i = 0; i < sBtns.length; i++) {
      sBtns[i].onclick = (function (b) {
        return function () {
          selStatus = b.getAttribute('data-s');
          for (var j = 0; j < sBtns.length; j++) sBtns[j].classList.remove('sel');
          b.classList.add('sel');
        };
      })(sBtns[i]);
    }
    pop.querySelector('.ep-save').onclick = function () {
      var p = faToEn(priceInput.value).replace(/[^\d]/g, '');
      var entry = {};
      if (selStatus) entry.s = selStatus;
      if (p !== '') entry.p = parseInt(p, 10);
      if (entry.s || entry.p !== undefined) EDITS[keyOf(rid, d)] = entry;
      else delete EDITS[keyOf(rid, d)];
      save(); applyAll(); updCount(); refreshRevenue(); closePop();
    };
    pop.querySelector('.ep-default').onclick = function () {
      delete EDITS[keyOf(rid, d)];
      save(); applyAll(); updCount(); refreshRevenue(); closePop();
    };
    pop.querySelector('.ep-cancel').onclick = closePop;
    setTimeout(function () { priceInput.focus(); }, 10);
  }
  /* ---------- cell click (only in edit mode) ---------- */
  document.addEventListener('click', function (e) {
    if (pop && !pop.contains(e.target) && e.target !== pop) closePop();
  });
  document.addEventListener('click', function (e) {
    if (!on) return;
    var t = e.target;
    var td = t.closest ? t.closest('td.c[data-r][data-d]') : null;
    if (!td) return;
    e.preventDefault();
    openPop(td);
  });

  /* ---------- revenue refresh hook (set by rev_js) ---------- */
  function refreshRevenue() { if (window.__revRender) window.__revRender(); }

  /* ---------- manager: count / export / import / reset ---------- */
  var mgr = document.createElement('div');
  mgr.id = 'editMgr';
  mgr.innerHTML =
    "<span class='edit-count'></span>" +
    "<button id='editExport' title='دانلود فایل JSON ویرایش‌های دستی'>📥 دانلود ویرایش‌ها</button>" +
    "<button id='editImport' title='بارگذاری فایل JSON ویرایش‌ها'>📤 بارگذاری</button>" +
    "<button id='editReset' title='حذف همه ویرایش‌های دستی'>🗑️ پاک کردن</button>" +
    "<input type='file' id='editFile' accept='.json' style='display:none'>";
  var hd = document.querySelector('.hd-actions');
  if (hd && hd.parentNode) hd.parentNode.insertBefore(mgr, hd.nextSibling);

  function updCount() {
    var c = document.querySelector('.edit-count');
    if (c) c.textContent = 'ویرایش‌های دستی: ' + window.RE.count();
  }
  mgr.querySelector('#editExport').onclick = function () {
    var blob = new Blob([JSON.stringify(EDITS, null, 1)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'radar-edits-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 300);
  };
  mgr.querySelector('#editImport').onclick = function () { document.getElementById('editFile').click(); };
  mgr.querySelector('#editFile').addEventListener('change', function () {
    var f = this.files[0];
    if (!f) return;
    var rd = new FileReader();
    rd.onload = function () {
      try {
        var data = JSON.parse(rd.result);
        if (typeof data !== 'object' || data === null) throw new Error('bad');
        EDITS = data;
        save(); applyAll(); updCount(); refreshRevenue();
        alert('بارگذاری شد: ' + Object.keys(EDITS).length + ' ویرایش');
      } catch (err) { alert('فایل JSON نامعتبر است'); }
    };
    rd.readAsText(f);
    this.value = '';
  });
  mgr.querySelector('#editReset').onclick = function () {
    if (!confirm('همه ویرایش‌های دستی پاک شوند؟')) return;
    EDITS = {}; save(); applyAll(); updCount(); refreshRevenue(); closePop();
  };

  /* ---------- init ---------- */
  setMode(false);
  applyAll();
  updCount();
})();