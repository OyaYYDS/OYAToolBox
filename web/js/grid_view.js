/**
 * grid_view.js - 网格视图渲染与交互
 */

const GridView = (() => {
  let container = null;
  let tools = [];
  let selectedId = null;
  let onSelect = null;
  let onLaunch = null;
  let onContextMenu = null;
  let onReorder = null;
  let iconSize = 48;
  let sizeMode = 'medium';

  // ─── 初始化 ─────────────────────────────────────────────────────────────

  function init(opts) {
    container = document.getElementById('grid-view');
    onSelect      = opts.onSelect;
    onLaunch      = opts.onLaunch;
    onContextMenu = opts.onContextMenu;
    onReorder     = opts.onReorder;

    _bindContainerEvents();
  }

  // ─── 渲染 ────────────────────────────────────────────────────────────────

  function render(toolList) {
    tools = toolList;
    if (!container) return;

    if (tools.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="width:100%;justify-content:center">
          <div class="empty-icon"><img src="img/logo.png" alt="应用图标" draggable="false" style="width:100px;height:100px;object-fit:contain;opacity:.6"></div>
          <div class="empty-title">还没有软件</div>
          <div class="empty-hint">点击"添加软件"或<br>将文件拖到此处开始使用</div>
        </div>`;
      return;
    }

    container.innerHTML = '';
    _applySizeClass();
    tools.forEach(tool => {
      container.appendChild(_buildItem(tool));
    });

    // 启动拖拽排序
    DragSort.rebind('#grid-view', '.tool-item', 'id');
  }

  function _buildItem(tool) {
    const div = document.createElement('div');
    div.className = 'tool-item';
    div.dataset.id = tool.id;
    if (tool.id === selectedId) div.classList.add('selected');

    div.innerHTML = `
      <div class="item-icon">${_iconHtml(tool, iconSize)}</div>
      <div class="item-name" title="${_esc(tool.name)}">${_esc(tool.name)}</div>
    `;
    return div;
  }

  // ─── 事件绑定 ─────────────────────────────────────────────────────────────

  function _bindContainerEvents() {
    if (!container) return;

    // 单击选中
    container.addEventListener('click', (e) => {
      const item = e.target.closest('.tool-item');
      if (!item) {
        _clearSelection();
        HoverCard.unlock();
        return;
      }
      const id = item.dataset.id;
      _select(id);
      if (onSelect) onSelect(id);
    });

    // 双击启动
    container.addEventListener('dblclick', (e) => {
      const item = e.target.closest('.tool-item');
      if (!item) return;
      if (onLaunch) onLaunch(item.dataset.id);
    });

    // 回车启动
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && selectedId && container.style.display !== 'none') {
        if (onLaunch) onLaunch(selectedId);
      }
    });

    // 右键菜单
    container.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const item = e.target.closest('.tool-item');
      if (!item) return;
      const id = item.dataset.id;
      const tool = tools.find(t => t.id === id);
      _select(id);
      HoverCard.cancelShow();
      HoverCard.cancelHide();
      if (tool) HoverCard.show(tool, e.clientX, e.clientY);
      HoverCard.lock(id);
      if (onContextMenu) onContextMenu(id, e.clientX, e.clientY);
    });

    // 鼠标悬停 - hover card
    container.addEventListener('mouseover', (e) => {
      const item = e.target.closest('.tool-item');
      if (!item) return;
      if (HoverCard.isLocked()) return;
      const id = item.dataset.id;
      const tool = tools.find(t => t.id === id);
      if (!tool) return;
      const rect = item.getBoundingClientRect();
      HoverCard.scheduleShow(tool, rect.right, rect.top, 0);
    });

    container.addEventListener('mouseout', (e) => {
      const item = e.target.closest('.tool-item');
      if (!item) return;
      if (HoverCard.isLocked()) return;
      HoverCard.cancelShow();
      HoverCard.scheduleHide(300);
    });

    // 拖拽排序由 DragSort 统一处理，此处不需要重复绑定
  }

  // ─── 公开方法 ─────────────────────────────────────────────────────────────

  function select(id) { _select(id); }
  function getSelected() { return selectedId; }

  function updateIcon(toolId, iconData) {
    const item = container?.querySelector(`[data-id="${toolId}"]`);
    if (!item) return;
    const iconEl = item.querySelector('.item-icon');
    if (!iconEl) return;

    const tool = tools.find(t => t.id === toolId);
    if (!tool) return;
    tool.icon_data = iconData;

    iconEl.innerHTML = _iconHtml(tool, iconSize);
    HoverCard.updateIconForTool(toolId, iconData);
  }

  function setIconSize(mode) {
    const map = { small: 40, medium: 48, large: 64 };
    sizeMode = map[mode] ? mode : 'medium';
    iconSize = map[sizeMode];
    _applySizeClass();
  }

  function updateTool(tool) {
    const idx = tools.findIndex(t => t.id === tool.id);
    if (idx >= 0) tools[idx] = tool;
    const item = container?.querySelector(`[data-id="${tool.id}"]`);
    if (item) {
      const newItem = _buildItem(tool);
      item.replaceWith(newItem);
    }
  }

  function removeTool(toolId) {
    tools = tools.filter(t => t.id !== toolId);
    container?.querySelector(`[data-id="${toolId}"]`)?.remove();
    if (selectedId === toolId) selectedId = null;
  }

  // ─── 内部工具 ─────────────────────────────────────────────────────────────

  function _select(id) {
    if (selectedId) {
      container?.querySelector(`[data-id="${selectedId}"]`)?.classList.remove('selected');
    }
    selectedId = id;
    container?.querySelector(`[data-id="${id}"]`)?.classList.add('selected');
  }

  function _clearSelection() {
    if (selectedId) {
      container?.querySelector(`[data-id="${selectedId}"]`)?.classList.remove('selected');
    }
    selectedId = null;
  }

  function _iconHtml(tool, size) {
    if (tool.icon_data && tool.icon_mode !== 'text') {
      const src = window.iconDataToSrc(tool.icon_data);
      if (src) {
        return `<img src="${src}" width="${size}" height="${size}" draggable="false" style="border-radius:6px;object-fit:contain;pointer-events:none" alt="">`;
      }
    }
    const abbr  = (tool.icon_text  || tool.name?.substring(0,2) || '?').substring(0,2).toUpperCase();
    const color = tool.icon_color || '#4a9eff';
    const fs    = Math.floor(size * 0.35);
    return `<div class="text-icon" style="background:${color};width:${size}px;height:${size}px;font-size:${fs}px">${abbr}</div>`;
  }

  function _esc(str) {
    return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function _applySizeClass() {
    if (!container) return;
    container.classList.remove('size-small', 'size-medium', 'size-large');
    container.classList.add('size-' + sizeMode);
  }

  return { init, render, select, getSelected, updateIcon, updateTool, removeTool, setIconSize };
})();
