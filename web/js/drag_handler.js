/**
 * drag_handler.js - 窗口缩放光标提示 + 工具项拖拽排序
 *
 * 窗口拖动: pywebview 内置 drag region 机制 (#titlebar-drag, 原生回调移动窗口)
 * 窗口缩放: pywebview frameless 窗口原生边缘缩放 (本文件只负责光标提示)
 */

// ─── 窗口缩放光标提示（缩放本身由 pywebview frameless 原生处理）────────────────

const WindowResize = (() => {
  const EDGE = 6;

  function init() {
    document.addEventListener('mousemove', updateCursor);
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
