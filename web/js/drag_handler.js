/**
 * drag_handler.js - 窗口缩放光标提示 + 工具项拖拽排序
 *
 * 窗口拖动: pywebview 内置 drag region 机制 (#titlebar-drag, 原生回调移动窗口)
 * 窗口缩放: pywebview frameless 窗口原生边缘缩放 (本文件只负责光标提示)
 */

// ─── 窗口缩放 ────────────────────────────────────────────────────────────────
// 双保险: WM_NCHITTEST 原生路径未接管时 (页面仍能收到 mousemove),
// 由 JS 直接调用 pywebview 的 window.resize 驱动缩放 (硬件加速下流畅)

const WindowResize = (() => {
  const EDGE = 6;
  const MIN_W = 800, MIN_H = 500;

  let resizing = false;
  let edge = '';
  let startX = 0, startY = 0;
  let startWin = null;   // [x, y, w, h] 物理像素基准 (mousedown 时异步获取)

  function init() {
    document.addEventListener('mousemove', updateCursor);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('mouseup', onUp);
  }

  function _getEdge(e) {
    const x = e.clientX, y = e.clientY;
    const w = window.innerWidth, h = window.innerHeight;
    let h_edge = '', v_edge = '';
    if (x < EDGE) h_edge = 'left';
    else if (x > w - EDGE) h_edge = 'right';
    if (y < EDGE) v_edge = 'top';
    else if (y > h - EDGE) v_edge = 'bottom';
    return (v_edge + h_edge) || '';
  }

  function updateCursor(e) {
    const e2 = _getEdge(e);
    const cursors = {
      'top': 'n-resize', 'bottom': 's-resize',
      'left': 'w-resize', 'right': 'e-resize',
      'topleft': 'nw-resize', 'topright': 'ne-resize',
      'bottomleft': 'sw-resize', 'bottomright': 'se-resize',
    };
    document.body.style.cursor = cursors[e2] || '';
  }

  function onDown(e) {
    if (e.button !== 0) return;
    const e2 = _getEdge(e);
    if (!e2) return;
    resizing = true;
    edge = e2;
    startX = e.screenX;
    startY = e.screenY;
    startWin = null;
    e.preventDefault();
    // 异步取窗口物理位置/尺寸作为缩放基准 (CSS 像素与物理像素在缩放屏下不一致)
    window.AppBridge?.getWindowSize().then((str) => {
      const r = JSON.parse(str || '[0,0,0,0]');
      if (r[2] > 0) startWin = r;
    }).catch(() => {});
  }

  function onMove(e) {
    if (!resizing || !startWin) return;
    const dx = e.screenX - startX;
    const dy = e.screenY - startY;
    let nx = startWin[0], ny = startWin[1];
    let nw = startWin[2], nh = startWin[3];

    // 各边缘锚点: 右/下只改尺寸; 左/上改尺寸同时移动位置 (对边保持不动)
    if (edge.includes('right'))  nw = startWin[2] + dx;
    if (edge.includes('left')) {
      nw = startWin[2] - dx;
      nx = startWin[0] + dx;
    }
    if (edge.includes('bottom')) nh = startWin[3] + dy;
    if (edge.includes('top')) {
      nh = startWin[3] - dy;
      ny = startWin[1] + dy;
    }

    // 最小尺寸钳制 (左/上边缘要同步回推位置, 保证对边锚点不动)
    if (nw < MIN_W) {
      if (edge.includes('left')) nx = startWin[0] + startWin[2] - MIN_W;
      nw = MIN_W;
    }
    if (nh < MIN_H) {
      if (edge.includes('top')) ny = startWin[1] + startWin[3] - MIN_H;
      nh = MIN_H;
    }

    window.AppBridge?.setWindowRect(Math.round(nx), Math.round(ny), Math.round(nw), Math.round(nh));
  }

  function onUp() {
    resizing = false;
    edge = '';
    startWin = null;
  }

  return { init };
})();


// ─── 工具项拖拽排序（鼠标事件版）─────────────────────────────────────────────
// 使用 mousedown/mousemove/mouseup 替代 HTML5 Drag API，
// 避免与 OS 级文件拖放事件冲突（旧版拖拽会误触发"添加工具"对话框）。

const DragSort = (() => {
  const THRESHOLD = 6;          // px - 超过此距离才视为拖拽
  const containers = new Map(); // Map<HTMLElement, {itemSel, idAttr}>
  let onReorder     = null;

  let dragItem      = null;
  let dragContainer = null;
  let dragItemSel   = null;
  let isDragging    = false;
  let suppressClick = false;    // drag 完成后阻止误触 click
  let lastMX = 0, lastMY = 0;  // 最后鼠标位置

  // ── 全局文档级事件（只绑定一次）─────────────────────────────────────────────
  document.addEventListener('mousedown', _onDown);
  document.addEventListener('mousemove', _onMove);
  document.addEventListener('mouseup',   _onUp);

  // 捕获阶段拦截 click，阻止拖拽结束后误触发选中/启动
  document.addEventListener('click', (e) => {
    if (suppressClick) {
      e.stopPropagation();
      e.preventDefault();
      suppressClick = false;
    }
  }, true);

  function _onDown(e) {
    if (e.button !== 0) return;
    for (const [container, { itemSel }] of containers) {
      if (!container.isConnected) continue;
      const item = e.target.closest(itemSel);
      if (item && container.contains(item)) {
        dragItem      = item;
        dragContainer = container;
        dragItemSel   = itemSel;
        isDragging    = false;
        lastMX = e.clientX;
        lastMY = e.clientY;
        // 阻止浏览器原生图片/元素拖拽
        e.preventDefault();
        return;
      }
    }
  }

  function _onMove(e) {
    if (!dragItem) return;
    const dist = Math.hypot(e.clientX - lastMX, e.clientY - lastMY);
    if (!isDragging) {
      if (dist < THRESHOLD) return;
      isDragging = true;
      dragItem.classList.add('drag-source');
      document.body.style.cursor = 'grabbing';
    }
    e.preventDefault();
    lastMX = e.clientX;
    lastMY = e.clientY;
    _updateIndicators(e.clientX, e.clientY);
  }

  function _updateIndicators(mx, my) {
    _clearIndicators();
    const items  = [...dragContainer.querySelectorAll(dragItemSel)];
    const isGrid = dragContainer.id === 'grid-view';
    for (const item of items) {
      if (item === dragItem) continue;
      const r = item.getBoundingClientRect();
      if (mx >= r.left && mx <= r.right && my >= r.top && my <= r.bottom) {
        const mid = isGrid ? r.left + r.width / 2 : r.top + r.height / 2;
        const pos = isGrid ? mx : my;
        item.classList.add(pos < mid ? 'drag-over-before' : 'drag-over-after');
        return;
      }
    }
  }

  function _onUp() {
    if (!dragItem) return;
    if (isDragging) {
      _doReorder(lastMX, lastMY);
      suppressClick = true;
    }
    _reset();
  }

  function _doReorder(mx, my) {
    const items  = [...dragContainer.querySelectorAll(dragItemSel)];
    const isGrid = dragContainer.id === 'grid-view';
    let targetItem   = null;
    let insertBefore = true;

    for (const item of items) {
      if (item === dragItem) continue;
      const r = item.getBoundingClientRect();
      if (mx >= r.left && mx <= r.right && my >= r.top && my <= r.bottom) {
        targetItem   = item;
        const mid    = isGrid ? r.left + r.width / 2 : r.top + r.height / 2;
        insertBefore = (isGrid ? mx : my) < mid;
        break;
      }
    }
    if (!targetItem) return;

    if (insertBefore) {
      dragContainer.insertBefore(dragItem, targetItem);
    } else {
      targetItem.after(dragItem);
    }

    const newOrder = [...dragContainer.querySelectorAll(dragItemSel)]
      .map(el => el.getAttribute('data-id'));
    if (onReorder) onReorder(newOrder);
  }

  function _clearIndicators() {
    if (!dragContainer) return;
    dragContainer.querySelectorAll(dragItemSel).forEach(el => {
      el.classList.remove('drag-over-before', 'drag-over-after', 'drag-over');
    });
  }

  function _reset() {
    if (dragItem) dragItem.classList.remove('drag-source');
    _clearIndicators();
    document.body.style.cursor = '';
    dragItem      = null;
    dragContainer = null;
    dragItemSel   = null;
    isDragging    = false;
  }

  function _register(containerSel, itemSel, idAttr) {
    const el = document.querySelector(containerSel);
    if (el) containers.set(el, { itemSel, idAttr });
  }

  function init(containerSel, itemSel, idAttr, reorderCb) {
    onReorder = reorderCb;
    _register(containerSel, itemSel, idAttr);
  }

  /** 注册新容器（视图切换/DOM 重建后调用，不重复绑定事件）*/
  function rebind(containerSel, itemSel, idAttr) {
    _register(containerSel, itemSel, idAttr);
  }

  return { init, rebind };
})();
