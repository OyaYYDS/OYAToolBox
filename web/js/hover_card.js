/**
 * hover_card.js - Grid 模式下的鼠标悬停信息卡
 */

const HoverCard = (() => {
  let el = null;
  let locked = false;
  let lockId = null;
  let showTimer = null;
  let hideTimer = null;
  let currentId = null;

  function init() {
    el = document.getElementById('hover-card');
    if (!el) return;

    // 点击空白区域解锁
    document.addEventListener('mousedown', (e) => {
      if (locked && !el.contains(e.target)) {
        unlock();
      }
    });

    // 鼠标离开卡片时（非锁定状态）延迟隐藏
    el.addEventListener('mouseleave', () => {
      if (!locked) scheduleHide(300);
    });
    el.addEventListener('mouseenter', () => {
      if (!locked) cancelHide();
    });
  }

  function show(tool, x, y) {
    if (!el) return;
    cancelHide();
    currentId = tool.id;
    _render(tool);
    _position(x, y);
    el.classList.remove('hidden');
  }

  function scheduleShow(tool, x, y, delay = 400) {
    cancelShow();
    showTimer = setTimeout(() => show(tool, x, y), delay);
  }

  function scheduleHide(delay = 250) {
    cancelHide();
    hideTimer = setTimeout(hide, delay);
  }

  function cancelShow() {
    if (showTimer) { clearTimeout(showTimer); showTimer = null; }
  }

  function cancelHide() {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
  }

  function hide() {
    if (!el || locked) return;
    el.classList.add('hidden');
    currentId = null;
  }

  function lock(id) {
    if (!el) return;
    locked = true;
    lockId = id;
    el.classList.add('locked');
    cancelHide();
  }

  function unlock() {
    if (!el) return;
    locked = false;
    lockId = null;
    el.classList.remove('locked');
    scheduleHide(100);
  }

  function isLocked() { return locked; }
  function getLockId() { return lockId; }

  function _render(tool) {
    const iconHtml = _iconHtml(tool, 36);
    const desc = tool.description || '暂无描述';
    const path = tool.path || '';

    el.innerHTML = `
      <div class="hc-header">
        <div class="hc-icon">${iconHtml}</div>
        <div class="hc-name" title="${_esc(tool.name)}">${_esc(tool.name)}</div>
      </div>
      <div class="hc-desc">${_esc(desc)}</div>
      ${path ? `<div class="hc-path" title="${_esc(path)}">${_esc(path)}</div>` : ''}
      <div class="hc-actions">
        <button class="hc-btn launch" data-action="launch" data-id="${tool.id}">
          ▶ 启动
        </button>
        <button class="hc-btn" data-action="edit" data-id="${tool.id}">
          ✏ 编辑
        </button>
        <button class="hc-btn" data-action="cancel">
          ✕
        </button>
      </div>
    `;

    // 按钮事件
    el.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        const id = btn.dataset.id;
        if (action === 'launch' && id) {
          window.App?.launchTool(id);
        } else if (action === 'edit' && id) {
          window.App?.editTool(id);
        }
        unlock();
      });
    });
  }

  function _position(mx, my) {
    if (!el) return;
    el.style.visibility = 'hidden';
    el.classList.remove('hidden');

    const cardW = el.offsetWidth || 240;
    const cardH = el.offsetHeight || 200;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left = mx + 14;
    let top  = my + 14;

    if (left + cardW > vw - 12) left = mx - cardW - 10;
    if (top  + cardH > vh - 12) top  = my - cardH - 10;
    if (left < 8) left = 8;
    if (top  < 8) top  = 8;

    el.style.left = left + 'px';
    el.style.top  = top  + 'px';
    el.style.visibility = '';
  }

  function updateIconForTool(toolId, iconData) {
    if (currentId !== toolId || !el) return;
    const imgEl = el.querySelector(`.hc-icon img[data-id="${toolId}"]`);
    if (imgEl && iconData) {
      imgEl.src = _iconSrc(iconData);
    }
  }

  function _iconHtml(tool, size) {
    if (tool.icon_data && tool.icon_mode !== 'text') {
      const src = window.iconDataToSrc(tool.icon_data);
      if (src) {
        return `<img data-id="${tool.id}" src="${src}" width="${size}" height="${size}" draggable="false" style="border-radius:6px;pointer-events:none">`;
      }
    }
    const abbr = tool.icon_text || tool.name?.substring(0, 2).toUpperCase() || '?';
    const color = tool.icon_color || '#4a9eff';
    return `<div class="text-icon" style="background:${color};width:${size}px;height:${size}px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:${Math.floor(size*0.35)}px;font-weight:700;color:#fff;">${abbr}</div>`;
  }

  function _iconSrc(data) {
    return window.iconDataToSrc(data);
  }

  function _esc(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { init, show, scheduleShow, scheduleHide, cancelShow, cancelHide, hide,
           lock, unlock, isLocked, getLockId, updateIconForTool };
})();
