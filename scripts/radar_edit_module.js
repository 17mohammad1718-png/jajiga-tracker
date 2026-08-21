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
    '#editMgr button:hover{border-color:#38bdf8;color:#fff;}' +
    '.drag-btn.active,.edit-btn.active{background:linear-gradient(135deg,#f59e0b,#b45309)!important;box-shadow:0 4px 14px rgba(245,158,11,.35)!important;}' +
    '.cal td.c.sel{outline:2px solid #f59e0b;outline-offset:-2px;}' +
    'body.drag-active{user-select:none;-webkit-user-select:none;}' +
    '.drag-badge{position:fixed;z-index:80;background:#111f35;border:1px solid #f59e0b;border-radius:10px;padding:7px 12px;font-size:12px;color:#e2e8f0;box-shadow:0 10px 30px rgba(0,0,0,.5);pointer-events:none;white-space:nowrap;}' +
    '.drag-badge b{color:#fbbf24;font-size:13px;}';
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

  /* ---------- drag-to-select revenue range (default ON; toggle to disable) ---------- */
  var DRAG_KEY = 'radar_drag_v1';
  var MODE_KEY = 'radar_mode_v1';
  var dragOn = true;
  try { dragOn = localStorage.getItem(DRAG_KEY) !== '0'; } catch (e) {}
  var dragMode = 'free'; /* 'free' = آزاد (هر تعداد ردیف لمس‌شده) | 'single' = تکی (همان ردیف شروع) */
  try { var _m = localStorage.getItem(MODE_KEY); if (_m === 'single') dragMode = 'single'; } catch (e) {}
  var dragBtn = document.createElement('button');
  dragBtn.id = 'dragToggleBtn';
  dragBtn.className = 'export-btn drag-btn';
  dragBtn.title = 'انتخاب بازه درآمد با کشیدن موس روی جدول — فعال/غیرفعال';
  if (exp && exp.parentNode) exp.parentNode.appendChild(dragBtn);
  var modeBtn = document.createElement('button');
  modeBtn.id = 'dragModeBtn';
  modeBtn.className = 'export-btn drag-btn active';
  modeBtn.title = 'حالت محاسبه بازه: آزاد = هر تعداد ردیفی که لمس کنی | تکی = فقط همان ردیف شروع کشیدن';
  if (exp && exp.parentNode) exp.parentNode.appendChild(modeBtn);
  function updDragLabel() {
    dragBtn.textContent = dragOn ? '🎯 بازه: روشن' : '🎯 بازه: خاموش';
    dragBtn.classList.toggle('active', dragOn);
  }
  function updModeLabel() {
    modeBtn.textContent = dragMode === 'single' ? '🧮 حالت: تکی' : '🧮 حالت: آزاد';
  }
  dragBtn.onclick = function () {
    dragOn = !dragOn;
    try { localStorage.setItem(DRAG_KEY, dragOn ? '1' : '0'); } catch (e) {}
    updDragLabel();
  };
  modeBtn.onclick = function () {
    dragMode = dragMode === 'single' ? 'free' : 'single';
    try { localStorage.setItem(MODE_KEY, dragMode); } catch (e) {}
    updModeLabel();
    /* حداکثر یک کلبه در حالت تکی: همان اولین کلبهٔ انتخاب‌شده فعلی */
    if (window.__revSetMode) window.__revSetMode(dragMode);
  };
  updDragLabel();
  updModeLabel();

  var dragging = false, dStart = null, dLast = null, badge = null, lastX = 0, lastY = 0;
  var dragRid = null, dragLabel = '', touched = {}; /* touched: rid -> true */
  var selCache = {}; /* 'r|d' -> bool: کش وضعیت هایلایت برای روون‌تر شدن */
  function cellDate(td) { return td ? td.getAttribute('data-d') : null; }
  function cellRid(td) { return td ? td.getAttribute('data-r') : null; }
  function jlabelOf(td) {
    if (!td) return '';
    var t = td.getAttribute('title') || '';
    return t.split(' · ')[0] || td.getAttribute('data-d') || '';
  }
  function setDragHighlight(lo, hi) {
    var cells = document.querySelectorAll('td.c[data-d]');
    for (var i = 0; i < cells.length; i++) {
      var td = cells[i];
      var d = td.getAttribute('data-d');
      var r = td.getAttribute('data-r');
      /* فقط سلول‌هایی هایلایت می‌شوند که هم در بازه تاریخ باشند هم در ردیف(های) لمس‌شده */
      var on = !!(lo && hi && d >= lo && d <= hi && inSelection(td));
      var key = r + '|' + d;
      if (selCache[key] === on) continue; /* بدون تغییر = بدون لمس DOM -> روون‌تر */
      selCache[key] = on;
      td.classList.toggle('sel', on);
    }
  }
  function inSelection(td) {
    if (!dragRid && !Object.keys(touched).length) return true; /* fallback: همه */
    if (dragMode === 'single') return cellRid(td) === dragRid;
    return !!touched[cellRid(td)];
  }
  function updateBadge(lo, hi, sTd, eTd) {
    if (!badge) {
      badge = document.createElement('div');
      badge.className = 'drag-badge';
      document.body.appendChild(badge);
    }
    var cells = document.querySelectorAll('td.c[data-d].sel');
    var booked = 0, free = 0, sum = 0;
    for (var i = 0; i < cells.length; i++) {
      var td = cells[i];
      if (!inSelection(td)) continue;
      if (td.classList.contains('booked')) {
        booked++;
        var pr = td.querySelector('.pr');
        if (pr) sum += parseInt(pr.textContent.replace(/[^0-9]/g, ''), 10) || 0;
      } else if (td.classList.contains('free')) free++;
    }
    var cnt = 0;
    for (var k in touched) { if (touched[k]) cnt++; }
    var head = (dragMode === 'single')
      ? 'کلبه: <b>' + (dragLabel || '—') + '</b>'
      : (cnt > 1 ? '<b>' + cnt + '</b> کلبه' : '<b>1</b> کلبه');
    badge.innerHTML = head + ' · از ' + jlabelOf(sTd) + ' تا ' + jlabelOf(eTd) +
      ' · <b>' + booked + '</b> شب پر · <b>' + free + '</b> خالی' +
      (sum ? ' · جمع‌تقریبی ≈ <b>' + sum.toLocaleString('en-US') + '</b> تومان' : '');
    badge.style.left = (lastX + 12) + 'px';
    badge.style.top = (lastY + 14) + 'px';
  }
  /* حرکت موس در حین کشیدن: هم mouseover و هم mousemove به اینجا می‌رسند.
     سلول زیر موس از event یا elementFromPoint پیدا می‌شود — حتی در حرکت سریع هیچ ردیفی جا نمی‌ماند. */
  function handleDragMove(e) {
    if (!dragging) return;
    var td = e && e.target && e.target.closest ? e.target.closest('td.c[data-d]') : null;
    if (!td && document.elementFromPoint && e) {
      var el = document.elementFromPoint(e.clientX, e.clientY);
      if (el && el.closest) td = el.closest('td.c[data-d]');
    }
    if (!td) return;
    var rid = cellRid(td), d = cellDate(td);
    var changed = false;
    if (rid) {
      if (dragMode === 'single') {
        if (!dragRid) { dragRid = rid; changed = true; }
      } else if (!touched[rid]) {
        touched[rid] = true; changed = true; /* آزاد: هر ردیف لمس‌شده اضافه می‌شود و ثابت می‌ماند */
      }
    }
    if (d && d !== dLast) { dLast = d; changed = true; }
    if (!changed) return;
    var lo = dStart < d ? dStart : d, hi = dStart < d ? d : dStart;
    setDragHighlight(lo, hi);
    var sTd = document.querySelector('td.c[data-d="' + lo + '"]');
    updateBadge(lo, hi, sTd, td);
  }
  document.addEventListener('mousedown', function (e) {
    if (!dragOn || on || e.button !== 0) return;
    var td = e.target.closest ? e.target.closest('td.c[data-d]') : null;
    if (!td) return;
    e.preventDefault();
    dragging = true;
    dStart = dLast = cellDate(td);
    dragRid = cellRid(td);
    touched = {};
    selCache = {}; /* شروع درگ جدید = وضعیت قبلی باطل است */
    if (dragRid && dragMode !== 'single') touched[dragRid] = true;
    var rowTd = td.parentNode ? td.parentNode.querySelector('.rname') : null;
    dragLabel = rowTd && rowTd.textContent ? rowTd.textContent.trim().replace(/\s+/g, ' ').slice(0, 60) : '';
    document.body.classList.add('drag-active');
    setDragHighlight(dStart, dLast);
    updateBadge(dStart, dLast, td, td);
  });
  var rafPend = false, lastEv = null;
  document.addEventListener('mouseover', function (e) { if (dragging) handleDragMove(e); });
  document.addEventListener('mousemove', function (e) {
    if (!dragging) return;
    lastX = e.clientX; lastY = e.clientY;
    lastEv = e;
    if (rafPend) return;
    rafPend = true;
    (window.requestAnimationFrame || function (cb) { setTimeout(cb, 16); })(function () {
      rafPend = false;
      handleDragMove(lastEv);
    });
  });
  document.addEventListener('mouseup', function () {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove('drag-active');
    if (badge) { badge.remove(); badge = null; }
    if (dStart && dLast) {
      var lo = dStart < dLast ? dStart : dLast, hi = dStart < dLast ? dLast : dStart;
      var rids = [];
      for (var k in touched) { if (touched[k]) rids.push(k); }
      if (dragMode === 'single') rids = dragRid ? [dragRid] : rids;
      if (window.__revApplyRange) window.__revApplyRange(lo, hi, dragMode, rids);
    }
    dStart = dLast = null;
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { setDragHighlight(null, null); if (badge) { badge.remove(); badge = null; } }
  });

  /* ---------- init ---------- */
  setMode(false);
  applyAll();
  updCount();
})();