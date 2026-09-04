/**
 * app.js - 主应用控制器
 * 负责初始化、状态管理、视图切换、搜索、排序、分类筛选、右键菜单、toast 等
 */

(function () {
  'use strict';

  // ─── 全局状态 ──────────────────────────────────────────────────────────────
  let allTools    = [];
  let settings    = {};
  let viewMode    = 'grid';   // 'grid' | 'card'
  let sortBy      = 'manual';
  let filterCat   = '全部';
  let searchText  = '';
  let categories  = [];
  let contextMenuOpen = false;
  let gridIconSize = 'medium';
  let cardDetailHidden = false;
  let cardListWidth = 340;
  let searchDebounceTimer = null;

  // ─── 初始化 ────────────────────────────────────────────────────────────────

  async function init() {
    try {
      await initBridge();
    } catch (e) {
      console.error('Bridge init failed:', e);
      _showOfflineMode();
      return;
    }

    // 加载数据
    const [toolsStr, settingsStr, catsStr] = await Promise.all([
      window.AppBridge.getTools(),
      window.AppBridge.getSettings(),
      window.AppBridge.getCategories(),
    ]);

    allTools   = _parse(toolsStr)   || [];
    settings   = _parse(settingsStr)|| {};
    categories = _parse(catsStr)    || ['全部'];
    viewMode   = settings.view_mode  || 'grid';
    sortBy     = settings.sort_by   || 'manual';
    gridIconSize = settings.grid_icon_size || 'medium';
    cardDetailHidden = !!settings.card_detail_hidden;
    cardListWidth = settings.card_list_width || 340;

    // 应用设置
    SettingsPanel.applyAll(settings);
    SettingsPanel.init(_onSettingsChanged);

    // 初始化视图
    GridView.init({
      onSelect:      _onSelect,
      onLaunch:      launchTool,
      onContextMenu: _showContextMenu,
      onReorder:     _onReorder,
    });
    CardView.init({
      onLaunch:      launchTool,
      onEdit:        editTool,
      onDelete:      deleteTool,
      onContextMenu: _showContextMenu,
      onReorder:     _onReorder,
    });
    HoverCard.init();
    AddDialog.init(_onDialogSave);

    // 初始化拖拽排序（Grid 和 Card 列表）
    // 窗口拖动由 pywebview 内置 drag region 机制处理 (#titlebar-drag)
    DragSort.init('#grid-view', '.tool-item', 'id', _onReorder);
    DragSort.rebind('#card-list', '.tool-card', 'id');
    WindowResize.init();

    _renderCategoryBar();
    _updateDialogCategories();
    _initCardLayoutControls();
    _setGridSize(gridIconSize, false);
    _applyCardLayout(false);
    _switchView(viewMode, false);
    _renderTools();

    // 异步加载所有图标
    _requestAllIcons();

    // 绑定信号
    window.AppBridge.onToolsUpdated(_onToolsUpdated);
    window.AppBridge.onSettingsUpdated(_onSettingsUpdated);
    window.AppBridge.onIconLoaded(_onIconLoaded);
    window.AppBridge.onFilesDropped(_onFilesDropped);

    // 绑定 UI 事件
    _bindUIEvents();

    // 应用置顶设置
    if (settings.always_on_top) {
      window.AppBridge.setAlwaysOnTop(true);
      document.getElementById('btn-pin')?.classList.add('active');
    }

    // 系统主题监听
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (settings.theme === 'system') SettingsPanel.applyAll(settings);
    });
  }

  // ─── UI 事件绑定 ──────────────────────────────────────────────────────────

  function _bindUIEvents() {
    // OS 文件拖入遮罩 (WebView2 外部拖放会触发页面 drag 事件)
    let dragDepth = 0;
    const dropOverlay = document.getElementById('drop-overlay');
    document.addEventListener('dragenter', (e) => {
      e.preventDefault();
      dragDepth++;
      dropOverlay?.classList.add('visible');
    });
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('dragleave', () => {
      dragDepth--;
      if (dragDepth <= 0) {
        dragDepth = 0;
        dropOverlay?.classList.remove('visible');
      }
    });
    document.addEventListener('drop', (e) => {
      e.preventDefault();
      dragDepth = 0;
      dropOverlay?.classList.remove('visible');
    });

    // 标题栏按钮
    document.getElementById('btn-minimize')
      ?.addEventListener('click', () => window.AppBridge?.minimizeWindow());
    document.getElementById('btn-close')
      ?.addEventListener('click', () => window.AppBridge?.closeWindow());
    document.getElementById('btn-pin')
      ?.addEventListener('click', _togglePin);
    document.getElementById('btn-settings')
      ?.addEventListener('click', () => SettingsPanel.toggle());

    // 添加工具按钮
    document.getElementById('btn-add')
      ?.addEventListener('click', () => AddDialog.open());

    // 搜索 (120ms 防抖, 避免每个字符触发全量重建)
    const searchInput = document.getElementById('search-input');
    const searchClear = document.getElementById('search-clear');
    searchInput?.addEventListener('input', (e) => {
      searchText = e.target.value;
      searchClear?.classList.toggle('visible', !!searchText);
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(_renderTools, 120);
    });
    searchClear?.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      searchText = '';
      searchClear.classList.remove('visible');
      clearTimeout(searchDebounceTimer);
      _renderTools();
    });

    // 视图切换
    document.getElementById('btn-view-grid')
      ?.addEventListener('click', () => _switchView('grid'));
    document.getElementById('btn-view-card')
      ?.addEventListener('click', () => _switchView('card'));

    // 网格图标大小
    document.getElementById('btn-grid-small')
      ?.addEventListener('click', () => _setGridSize('small'));
    document.getElementById('btn-grid-medium')
      ?.addEventListener('click', () => _setGridSize('medium'));
    document.getElementById('btn-grid-large')
      ?.addEventListener('click', () => _setGridSize('large'));

    // 列表详情显隐
    document.getElementById('btn-card-detail-toggle')
      ?.addEventListener('click', _toggleCardDetail);

    // 排序菜单
    document.getElementById('btn-sort')
      ?.addEventListener('click', (e) => { e.stopPropagation(); _toggleSortMenu(); });

    // 关闭所有菜单
    document.addEventListener('click', _closeAllMenus);
    document.addEventListener('contextmenu', () => _closeContextMenu());
  }

  function _togglePin() {
    const pinBtn = document.getElementById('btn-pin');
    const isOn = !pinBtn?.classList.contains('active');
    pinBtn?.classList.toggle('active', isOn);
    window.AppBridge?.setAlwaysOnTop(isOn);
    settings.always_on_top = isOn;
    _saveSettings();
  }

  // ─── 分类栏 ───────────────────────────────────────────────────────────────

  function _renderCategoryBar() {
    const bar = document.getElementById('category-bar');
    if (!bar) return;

    const cats = ['全部', ...categories.filter(c => c !== '全部')];
    const counts = _countByCategory();

    bar.innerHTML = cats.map(cat => {
      const n = cat === '全部' ? allTools.length : (counts[cat] || 0);
      return `<button class="cat-tab${cat === filterCat ? ' active' : ''}" data-cat="${_escAttr(cat)}">
        ${_esc(cat)}<span class="cat-count">${n}</span>
      </button>`;
    }).join('');

    bar.querySelectorAll('.cat-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        filterCat = btn.dataset.cat;
        bar.querySelectorAll('.cat-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _renderTools();
      });
    });
  }

  function _updateDialogCategories() {
    const sel = document.getElementById('tool-category');
    if (!sel) return;
    const cats = categories.filter(c => c !== '全部');
    sel.innerHTML = cats.map(c => `<option value="${_escAttr(c)}">${_esc(c)}</option>`).join('');
  }

  function _countByCategory() {
    const counts = {};
    allTools.forEach(t => {
      counts[t.category] = (counts[t.category] || 0) + 1;
    });
    return counts;
  }

  // ─── 视图切换 ─────────────────────────────────────────────────────────────

  function _switchView(mode, save = true) {
    viewMode = mode;
    const gridV = document.getElementById('grid-view');
    const cardV = document.getElementById('card-view');
    const gridBtn = document.getElementById('btn-view-grid');
    const cardBtn = document.getElementById('btn-view-card');

    if (mode === 'grid') {
      if (gridV) gridV.style.display = '';
      if (cardV) cardV.style.display = 'none';
      gridBtn?.classList.add('active');
      cardBtn?.classList.remove('active');
    } else {
      if (gridV) gridV.style.display = 'none';
      if (cardV) cardV.style.display = '';
      gridBtn?.classList.remove('active');
      cardBtn?.classList.add('active');
    }

    _syncViewToolbar();

    if (save) {
      settings.view_mode = mode;
      _saveSettings();
    }
    _renderTools();
  }

  function _syncViewToolbar() {
    const switcher = document.getElementById('grid-size-switch');
    const sep = document.getElementById('sep-grid-size');
    const show = viewMode === 'grid';
    if (switcher) switcher.style.display = show ? 'inline-flex' : 'none';
    if (sep) sep.style.display = show ? '' : 'none';
  }

  function _setGridSize(size, save = true) {
    const valid = ['small', 'medium', 'large'];
    gridIconSize = valid.includes(size) ? size : 'medium';
    GridView.setIconSize(gridIconSize);

    const map = {
      small: document.getElementById('btn-grid-small'),
      medium: document.getElementById('btn-grid-medium'),
      large: document.getElementById('btn-grid-large'),
    };
    Object.entries(map).forEach(([k, el]) => el?.classList.toggle('active', k === gridIconSize));

    if (save) {
      settings.grid_icon_size = gridIconSize;
      _saveSettings();
    }
  }

  function _initCardLayoutControls() {
    const cardView = document.getElementById('card-view');
    const list = document.getElementById('card-list');
    const splitter = document.getElementById('card-splitter');
    if (!cardView || !list || !splitter) return;

    let dragging = false;
    let startX = 0;
    let startWidth = 0;

    splitter.addEventListener('mousedown', (e) => {
      dragging = true;
      startX = e.clientX;
      startWidth = list.getBoundingClientRect().width;
      document.body.style.cursor = 'col-resize';
      e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const next = Math.max(240, Math.min(760, startWidth + (e.clientX - startX)));
      cardListWidth = Math.round(next);
      cardView.style.setProperty('--card-list-width', cardListWidth + 'px');
    });

    window.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      document.body.style.cursor = '';
      settings.card_list_width = cardListWidth;
      _saveSettings();
    });
  }

  function _toggleCardDetail() {
    cardDetailHidden = !cardDetailHidden;
    _applyCardLayout();
  }

  function _applyCardLayout(save = true) {
    const cardView = document.getElementById('card-view');
    const btn = document.getElementById('btn-card-detail-toggle');
    if (!cardView) return;
    cardView.style.setProperty('--card-list-width', (cardListWidth || 340) + 'px');
    cardView.classList.toggle('detail-hidden', cardDetailHidden);
    if (btn) btn.textContent = cardDetailHidden ? '显示详情' : '隐藏详情';
    if (save) {
      settings.card_detail_hidden = cardDetailHidden;
      settings.card_list_width = cardListWidth;
      _saveSettings();
    }
  }

  // ─── 渲染工具列表 ──────────────────────────────────────────────────────────

  function _renderTools() {
    let list = [...allTools];

    // 分类筛选
    if (filterCat !== '全部') {
      list = list.filter(t => t.category === filterCat);
    }

    // 搜索过滤
    if (searchText) {
      const q = searchText.toLowerCase();
      list = list.filter(t =>
        t.name?.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q) ||
        t.path?.toLowerCase().includes(q) ||
        (t.tags || []).some(tag => tag.toLowerCase().includes(q))
      );
    }

    // 排序
    list = _sortTools(list, sortBy);

    if (viewMode === 'grid') {
      GridView.render(list);
    } else {
      CardView.render(list);
    }
  }

  function _sortTools(list, by) {
    switch (by) {
      case 'name_asc':  return [...list].sort((a,b) => (a.name||'').localeCompare(b.name||''));
      case 'name_desc': return [...list].sort((a,b) => (b.name||'').localeCompare(a.name||''));
      case 'created':   return [...list].sort((a,b) => (b.created_at||0) - (a.created_at||0));
      case 'last_used': return [...list].sort((a,b) => (b.last_used||0)  - (a.last_used||0));
      case 'use_count': return [...list].sort((a,b) => (b.use_count||0)  - (a.use_count||0));
      default:          return [...list].sort((a,b) => (a.order||0) - (b.order||0));
    }
  }

  // ─── 排序菜单 ─────────────────────────────────────────────────────────────

  const SORT_OPTIONS = [
    { key: 'manual',    label: '手动排序' },
    { key: 'name_asc',  label: '名称 A→Z' },
    { key: 'name_desc', label: '名称 Z→A' },
    { key: 'created',   label: '添加时间' },
    { key: 'last_used', label: '最近使用' },
    { key: 'use_count', label: '使用次数' },
  ];

  function _toggleSortMenu() {
    let menu = document.getElementById('sort-dropdown');
    if (menu) { menu.classList.toggle('hidden'); return; }

    menu = document.createElement('div');
    menu.id = 'sort-dropdown';
    menu.className = 'dropdown-menu';

    const btn = document.getElementById('btn-sort');
    const rect = btn.getBoundingClientRect();
    menu.style.cssText = `position:fixed;left:${rect.left}px;top:${rect.bottom + 4}px;z-index:250`;

    menu.innerHTML = SORT_OPTIONS.map(o => `
      <div class="dropdown-item ${sortBy === o.key ? 'active' : ''}" data-sort="${o.key}">
        <span class="di-check">✓</span> ${o.label}
      </div>`).join('');

    document.body.appendChild(menu);

    menu.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        sortBy = item.dataset.sort;
        settings.sort_by = sortBy;
        _saveSettings();
        _renderTools();
        menu.remove();
        const sortBtn = document.getElementById('btn-sort');
        if (sortBtn) {
          const cur = SORT_OPTIONS.find(o => o.key === sortBy);
          sortBtn.querySelector('.sort-label').textContent = cur?.label || '排序';
        }
      });
    });
  }

  function _closeAllMenus(e) {
    const sortMenu = document.getElementById('sort-dropdown');
    if (sortMenu && !document.getElementById('btn-sort')?.contains(e.target)) {
      sortMenu.remove();
    }
    _closeContextMenu();
  }

  // ─── 工具操作 ─────────────────────────────────────────────────────────────

  async function launchTool(id) {
    if (!window.AppBridge) return;
    const resultStr = await window.AppBridge.launchTool(id);
    const result = _parse(resultStr) || {};
    if (!result.ok) {
      toast(`启动失败: ${result.error}`, 'error');
    } else {
      // 更新使用次数（仅在 card 视图的详情中体现）
      const tool = allTools.find(t => t.id === id);
      if (tool) {
        tool.use_count = (tool.use_count || 0) + 1;
        tool.last_used = Date.now() / 1000;
        if (viewMode === 'card') CardView.updateTool(tool);
      }
    }
  }

  async function editTool(id) {
    const tool = allTools.find(t => t.id === id);
    if (!tool) return;
    AddDialog.openEdit(tool);
  }

  async function deleteTool(id) {
    const tool = allTools.find(t => t.id === id);
    if (!tool) return;
    if (!confirm(`确定删除"${tool.name}"？`)) return;
    if (!window.AppBridge) return;
    const resultStr = await window.AppBridge.deleteTool(id);
    const result = _parse(resultStr) || {};
    if (result.ok) {
      toast(`已删除: ${tool.name}`, 'success');
    } else {
      toast(`删除失败: ${result.error}`, 'error');
    }
  }

  function _onSelect(id) { /* 可扩展 */ }

  // ─── 拖拽排序回调 ─────────────────────────────────────────────────────────

  async function _onReorder(newIds) {
    if (!window.AppBridge) return;
    // 更新本地顺序
    const idxMap = {};
    newIds.forEach((id, i) => { idxMap[id] = i; });
    allTools.forEach(t => {
      if (idxMap[t.id] !== undefined) t.order = idxMap[t.id];
    });
    await window.AppBridge.reorderTools(JSON.stringify(newIds));
  }

  // ─── 对话框保存回调 ───────────────────────────────────────────────────────

  async function _onDialogSave(tool, mode, editId) {
    if (!window.AppBridge) return;
    if (mode === 'edit') {
      const resultStr = await window.AppBridge.updateTool(editId, JSON.stringify(tool));
      const result = _parse(resultStr) || {};
      if (!result.ok) toast(`保存失败: ${result.error}`, 'error');
    } else {
      const resultStr = await window.AppBridge.addTool(JSON.stringify(tool));
      const result = _parse(resultStr) || {};
      if (result.ok) {
        toast(`已添加: ${tool.name}`, 'success');
      } else {
        toast(`添加失败: ${result.error}`, 'error');
      }
    }
  }

  // ─── 信号处理 ─────────────────────────────────────────────────────────────

  function _onToolsUpdated(toolsJson) {
    allTools = _parse(toolsJson) || [];
    _renderCategoryBar();
    _renderTools();
    // 请求新增工具的图标
    allTools.forEach(t => {
      if (!t.icon_data && t.icon_mode !== 'text') {
        window.AppBridge?.requestIcon(t.id, t.path || '');
      }
    });
  }

  function _onSettingsUpdated(settingsJson) {
    const s = _parse(settingsJson) || {};
    settings = s;
    if (s.categories) {
      categories = s.categories;
      _renderCategoryBar();
      _updateDialogCategories();
      SettingsPanel.updateCategories(categories);
    }
  }

  function _onIconLoaded(toolId, iconData) {
    if (!iconData || toolId === '_preview') return;
    const tool = allTools.find(t => t.id === toolId);
    if (!tool) return;
    tool.icon_data = iconData;
    GridView.updateIcon(toolId, iconData);
    CardView.updateIcon(toolId, iconData);
  }

  function _onFilesDropped(pathsJson) {
    const paths = _parse(pathsJson) || [];
    if (!paths.length) return;
    // 隐藏拖入遮罩
    document.getElementById('drop-overlay')?.classList.remove('visible');
    AddDialog.prefillFromPaths(paths);
  }

  // ─── 右键菜单 ─────────────────────────────────────────────────────────────

  function _showContextMenu(toolId, x, y) {
    _closeContextMenu();
    contextMenuOpen = true;

    const menu = document.createElement('div');
    menu.id = 'context-menu';
    menu.style.left = x + 'px';
    menu.style.top  = y + 'px';

    menu.innerHTML = `
      <div class="ctx-item" data-action="launch"><span class="ctx-item-icon">▶</span>启动</div>
      <div class="ctx-item" data-action="edit">  <span class="ctx-item-icon">✏</span>编辑</div>
      <div class="ctx-separator"></div>
      <div class="ctx-item" data-action="location"><span class="ctx-item-icon">📂</span>打开所在位置</div>
      <div class="ctx-item" data-action="copy-path"><span class="ctx-item-icon">📋</span>复制路径</div>
      <div class="ctx-separator"></div>
      <div class="ctx-item danger" data-action="delete"><span class="ctx-item-icon">🗑</span>删除</div>
    `;

    document.body.appendChild(menu);

    // 边界检测
    requestAnimationFrame(() => {
      const rect = menu.getBoundingClientRect();
      if (rect.right  > window.innerWidth)  menu.style.left = (x - rect.width)  + 'px';
      if (rect.bottom > window.innerHeight) menu.style.top  = (y - rect.height) + 'px';
    });

    menu.querySelectorAll('.ctx-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = item.dataset.action;
        _closeContextMenu();
        HoverCard.unlock();
        switch (action) {
          case 'launch':    launchTool(toolId); break;
          case 'edit':      editTool(toolId); break;
          case 'delete':    deleteTool(toolId); break;
          case 'location':  window.AppBridge?.openFileLocation(toolId); break;
          case 'copy-path':
            window.AppBridge?.copyPath(toolId).then(() => toast('路径已复制', 'success'));
            break;
        }
      });
    });

    // 点击外部关闭
    setTimeout(() => {
      document.addEventListener('click', _closeContextMenu, { once: true });
    }, 0);
  }

  function _closeContextMenu() {
    const menu = document.getElementById('context-menu');
    if (menu) { menu.remove(); contextMenuOpen = false; }
  }

  // ─── 图标异步加载 ─────────────────────────────────────────────────────────

  function _requestAllIcons() {
    if (!window.AppBridge) return;
    allTools.forEach(t => {
      if (!t.icon_data || t.icon_mode === 'auto') {
        window.AppBridge.requestIcon(t.id, t.path || '');
      }
    });
  }

  // ─── 设置保存 ─────────────────────────────────────────────────────────────

  async function _onSettingsChanged(s) {
    settings = s;
    // 若分类列表有变化，刷新分类栏和对话框
    if (s.categories) {
      categories = s.categories;
      _renderCategoryBar();
      _updateDialogCategories();
      SettingsPanel.updateCategories(categories);
    }
    await _saveSettings();
  }

  async function _saveSettings() {
    if (!window.AppBridge) return;
    await window.AppBridge.saveSettings(JSON.stringify(settings));
  }

  // ─── Toast ────────────────────────────────────────────────────────────────

  function toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span class="toast-icon">${icons[type]||'ℹ'}</span>${_esc(msg)}`;
    container.appendChild(el);
    setTimeout(() => el.style.opacity = '0', 2500);
    setTimeout(() => el.remove(), 2800);
  }

  // ─── 离线/降级模式 ────────────────────────────────────────────────────────

  function _showOfflineMode() {
    const app = document.getElementById('app');
    if (app) {
      const errDiv = document.createElement('div');
      errDiv.style.cssText = 'color:var(--text-danger);padding:40px;text-align:center;font-size:16px';
      errDiv.textContent = '⚠ 无法连接到 Python 后端，请通过 main.py 启动';
      app.appendChild(errDiv);
    }
  }

  // ─── 工具 ────────────────────────────────────────────────────────────────

  function _parse(str) {
    if (!str) return null;
    try { return JSON.parse(str); } catch(e) { return null; }
  }

  function _esc(str) {
    return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function _escAttr(str) {
    return String(str||'').replace(/"/g,'&quot;');
  }

  // ─── 导出到全局 ──────────────────────────────────────────────────────────

  window.App = { init, launchTool, editTool, deleteTool, toast };

  // 启动
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
