/**
 * card_view.js - 卡片列表视图（横向长条 + 右侧详情）
 */

const CardView = (() => {
  let listEl     = null;
  let detailEl   = null;
  let tools      = [];
  let selectedId = null;
  let onLaunch   = null;
  let onEdit     = null;
  let onDelete   = null;
  let onContextMenu = null;
  let onReorder  = null;
  let eventsInit = false;  // 防止重复绑定事件

  // ─── 初始化 ─────────────────────────────────────────────────────────────

  function init(opts) {
    listEl   = document.getElementById('card-list');
    detailEl = document.getElementById('card-detail');
    onLaunch      = opts.onLaunch;
    onEdit        = opts.onEdit;
    onDelete      = opts.onDelete;
    onContextMenu = opts.onContextMenu;
    onReorder     = opts.onReorder;
    // 事件只绑定一次，利用事件委托对动态内容生效
    if (!eventsInit) {
      _bindListEvents();
      eventsInit = true;
    }
    DragSort.rebind('#card-list', '.tool-card', 'id');
  }

  // ─── 渲染 ────────────────────────────────────────────────────────────────

  function render(toolList) {
    tools = toolList;
    if (!listEl) return;

    if (tools.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state" style="margin:20px auto;text-align:center">
          <div class="empty-icon" style="font-size:36px">🧰</div>
          <div class="empty-title" style="font-size:14px;margin-top:8px">暂无工具</div>
        </div>`;
      _renderDetail(null);
      return;
    }

    listEl.innerHTML = '';
    tools.forEach(tool => {
      listEl.appendChild(_buildCard(tool));
    });

    // 保持选中
    if (selectedId) {
      _selectCard(selectedId, false);
    } else {
      _renderDetail(null);
    }
  }

  function _buildCard(tool) {
    const div = document.createElement('div');
    div.className = 'tool-card';
    div.dataset.id = tool.id;
    if (tool.id === selectedId) div.classList.add('selected');

    div.innerHTML = `
      <div class="card-icon">${_iconHtml(tool, 36)}</div>
      <div class="card-meta">
        <div class="card-name" title="${_esc(tool.name)}">${_esc(tool.name)}</div>
        <div class="card-desc">${_esc(tool.description || tool.path || '')}</div>
      </div>
      <button class="card-launch-btn" title="启动">▶</button>
    `;
    return div;
  }

  function _bindListEvents() {
    if (!listEl) return;
    // 使用事件委托，一次绑定即可对动态子元素生效
    listEl.addEventListener('click', (e) => {
      const launchBtn = e.target.closest('.card-launch-btn');
      if (launchBtn) {
        const card = launchBtn.closest('.tool-card');
        if (card && onLaunch) onLaunch(card.dataset.id);
        return;
      }
      const card = e.target.closest('.tool-card');
      if (card) _selectCard(card.dataset.id, true);
    });

    listEl.addEventListener('dblclick', (e) => {
      const card = e.target.closest('.tool-card');
      if (card && onLaunch) onLaunch(card.dataset.id);
    });

    listEl.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const card = e.target.closest('.tool-card');
      if (!card) return;
      _selectCard(card.dataset.id, true);
      if (onContextMenu) onContextMenu(card.dataset.id, e.clientX, e.clientY);
    });
  }

  // ─── 详情面板 ─────────────────────────────────────────────────────────────

  function _selectCard(id, renderDetail) {
    if (!listEl) return;
    listEl.querySelectorAll('.tool-card').forEach(c => c.classList.remove('selected'));
    const card = listEl.querySelector(`[data-id="${id}"]`);
    if (card) card.classList.add('selected');
    selectedId = id;
    if (renderDetail) {
      const tool = tools.find(t => t.id === id);
      _renderDetail(tool);
    }
  }

  function _renderDetail(tool) {
    if (!detailEl) return;
    if (!tool) {
      detailEl.className = 'empty';
      detailEl.innerHTML = '<div class="empty-hint">← 选择左侧工具查看详情<br>双击可直接启动</div>';
      return;
    }
    detailEl.className = '';

    const tagHtml = (tool.tags || []).map(t =>
      `<span class="tag-chip">${_esc(t)}</span>`
    ).join('');

    const lastUsed = tool.last_used
      ? new Date(tool.last_used * 1000).toLocaleString()
      : '从未';

    detailEl.innerHTML = `
      <div class="detail-icon-wrap">
        <div class="detail-icon">${_iconHtml(tool, 64)}</div>
        <div class="detail-title-group">
          <div class="detail-name">${_esc(tool.name)}</div>
          <div class="detail-category">${_esc(tool.category || '未分类')}</div>
        </div>
      </div>

      <div class="detail-actions">
        <button class="detail-btn primary" data-action="launch">▶ 启动</button>
        <button class="detail-btn secondary" data-action="edit">✏ 编辑</button>
        <button class="detail-btn secondary" data-action="location">📂 所在位置</button>
        <button class="detail-btn secondary" data-action="copy-path">📋 复制路径</button>
        <button class="detail-btn danger"    data-action="delete">🗑 删除</button>
      </div>

      ${tool.description ? `
      <div class="detail-section">
        <div class="detail-label">描述</div>
        <div class="detail-value">${_esc(tool.description)}</div>
      </div>` : ''}

      <div class="detail-section">
        <div class="detail-label">路径</div>
        <div class="detail-value clickable" data-action="location" title="点击打开所在位置">${_esc(tool.path)}</div>
      </div>

      ${tool.args ? `
      <div class="detail-section">
        <div class="detail-label">启动参数</div>
        <div class="detail-value">${_esc(tool.args)}</div>
      </div>` : ''}

      ${tool.work_dir ? `
      <div class="detail-section">
        <div class="detail-label">工作目录</div>
        <div class="detail-value">${_esc(tool.work_dir)}</div>
      </div>` : ''}

      ${tool.tags?.length ? `
      <div class="detail-section">
        <div class="detail-label">标签</div>
        <div class="detail-tags">${tagHtml}</div>
      </div>` : ''}

      <div class="detail-section">
        <div class="detail-label">统计</div>
        <div class="detail-value">使用 ${tool.use_count || 0} 次 · 最近使用：${lastUsed}</div>
      </div>
    `;

    // 绑定按钮事件
    detailEl.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.action;
        const id = tool.id;
        switch (action) {
          case 'launch':   if (onLaunch) onLaunch(id); break;
          case 'edit':     if (onEdit)   onEdit(id);   break;
          case 'delete':   if (onDelete) onDelete(id); break;
          case 'location': window.AppBridge?.openFileLocation(id); break;
          case 'copy-path':
            window.AppBridge?.copyPath(id).then(() => window.App?.toast('路径已复制', 'success'));
            break;
        }
      });
    });
  }

  // ─── 公开方法 ─────────────────────────────────────────────────────────────

  function updateIcon(toolId, iconData) {
    const tool = tools.find(t => t.id === toolId);
    if (!tool) return;
    tool.icon_data = iconData;

    const card = listEl?.querySelector(`[data-id="${toolId}"]`);
    if (card) {
      const iconEl = card.querySelector('.card-icon');
      if (iconEl) iconEl.innerHTML = _iconHtml(tool, 36);
    }

    if (selectedId === toolId) {
      const detailIcon = detailEl?.querySelector('.detail-icon');
      if (detailIcon) detailIcon.innerHTML = _iconHtml(tool, 64);
    }
  }

  function updateTool(tool) {
    const idx = tools.findIndex(t => t.id === tool.id);
    if (idx >= 0) tools[idx] = tool;
    const card = listEl?.querySelector(`[data-id="${tool.id}"]`);
    if (card) card.replaceWith(_buildCard(tool));
    if (selectedId === tool.id) _renderDetail(tool);
  }

  function removeTool(toolId) {
    tools = tools.filter(t => t.id !== toolId);
    listEl?.querySelector(`[data-id="${toolId}"]`)?.remove();
    if (selectedId === toolId) {
      selectedId = null;
      _renderDetail(null);
    }
  }

  function getSelected() { return selectedId; }

  // ─── 内部工具 ─────────────────────────────────────────────────────────────

  function _iconHtml(tool, size) {
    if (tool.icon_data && tool.icon_mode !== 'text') {
      const src = tool.icon_data.startsWith('svg:')
        ? 'data:image/svg+xml;base64,' + tool.icon_data.slice(4)
        : 'data:image/png;base64,' + tool.icon_data;
      return `<img src="${src}" width="${size}" height="${size}" draggable="false" style="border-radius:6px;object-fit:contain;pointer-events:none" alt="">`;
    }
    const abbr  = (tool.icon_text  || tool.name?.substring(0,2) || '?').substring(0,2).toUpperCase();
    const color = tool.icon_color || '#4a9eff';
    const fs    = Math.floor(size * 0.35);
    return `<div class="text-icon" style="background:${color};width:${size}px;height:${size}px;font-size:${fs}px">${abbr}</div>`;
  }

  function _esc(str) {
    return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { init, render, updateIcon, updateTool, removeTool, getSelected };
})();
