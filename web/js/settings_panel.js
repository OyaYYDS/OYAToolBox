/**
 * settings_panel.js - 设置侧边面板
 */

const SettingsPanel = (() => {
  let settings = {};
  let onChanged = null;

  function init(changeCallback) {
    onChanged = changeCallback;
    _bindEvents();
  }

  function open() {
    document.getElementById('settings-panel')?.classList.add('open');
  }

  function close() {
    document.getElementById('settings-panel')?.classList.remove('open');
  }

  function toggle() {
    const panel = document.getElementById('settings-panel');
    if (!panel) return;
    panel.classList.toggle('open');
  }

  function load(s) {
    settings = { ...s };
    _render();
  }

  function _render() {
    // 主题按钒
    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.themeTarget === (settings.theme || 'dark'));
    });

    // 始终置顶
    const topToggle = document.getElementById('toggle-always-on-top');
    if (topToggle) {
      topToggle.classList.toggle('on', !!settings.always_on_top);
    }

    // 分类列表
    _renderCategories();
  }

  function _bindEvents() {
    // 关闭按钮
    document.getElementById('settings-close')?.addEventListener('click', close);

    // 主题切换（读取 data-theme-target 避免 CSS 主题规则命中按钒本身）
    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        settings.theme = btn.dataset.themeTarget;
        _applyTheme(settings.theme);
        _render();
        _emit();
      });
    });

    // 始终置顶
    document.getElementById('toggle-always-on-top')?.addEventListener('click', function () {
      settings.always_on_top = !settings.always_on_top;
      this.classList.toggle('on', settings.always_on_top);
      window.AppBridge?.setAlwaysOnTop(settings.always_on_top);
      _emit();
    });

    // 添加分类
    document.getElementById('btn-add-category')?.addEventListener('click', _addCategory);
    document.getElementById('new-category-input')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') _addCategory();
    });
  }

  function _applyTheme(theme) {
    const resolvedTheme = theme === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme;
    // 同时设置在 <html> 和 #app，确保页面内所有 fixed 浮层（设置面板等）都能继承主题变量
    document.documentElement.setAttribute('data-theme', resolvedTheme);
    document.getElementById('app')?.setAttribute('data-theme', resolvedTheme);
  }

  function _emit() {
    if (onChanged) onChanged({ ...settings });
  }

  // ── 分类管理 ─────────────────────────────────────────────────────────────

  function _esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function _escAttr(s) {
    return String(s||'').replace(/"/g,'&quot;');
  }

  function _renderCategories() {
    const list = document.getElementById('categories-list');
    if (!list) return;
    const cats = (settings.categories || []).filter(c => c !== '全部');
    if (cats.length === 0) {
      list.innerHTML = '<div style="font-size:12px;color:var(--text-tertiary);padding:6px 0">暂无分类</div>';
      return;
    }
    list.innerHTML = cats.map(cat => `
      <div class="category-manage-item">
        <span>${_esc(cat)}</span>
        <button class="cat-del-btn" data-cat="${_escAttr(cat)}" title="删除分类">×</button>
      </div>
    `).join('');
    list.querySelectorAll('.cat-del-btn').forEach(btn => {
      btn.addEventListener('click', () => _deleteCategory(btn.dataset.cat));
    });
  }

  async function _addCategory() {
    const input = document.getElementById('new-category-input');
    const name = input?.value.trim();
    if (!name || name === '全部') return;
    if ((settings.categories || []).includes(name)) {
      input.value = '';
      return;
    }
    if (!window.AppBridge) return;
    const resultStr = await window.AppBridge.addCategory(name);
    try {
      const result = JSON.parse(resultStr);
      if (result.ok) {
        settings.categories = result.categories;
        input.value = '';
        _renderCategories();
        _emit();
      }
    } catch(e) {}
  }

  async function _deleteCategory(name) {
    if (!window.AppBridge) return;
    const resultStr = await window.AppBridge.deleteCategory(name);
    try {
      const result = JSON.parse(resultStr);
      if (result.ok) {
        settings.categories = result.categories;
        _renderCategories();
        _emit();
      }
    } catch(e) {}
  }

  /** 初次加载后应用所有视觉设置 */
  function applyAll(s) {
    load(s);
    _applyTheme(s.theme || 'dark');
  }

  function updateCategories(cats) {
    settings.categories = cats;
    _renderCategories();
  }

  return { init, open, close, toggle, load, applyAll, updateCategories };
})();
