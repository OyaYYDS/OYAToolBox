/**
 * add_dialog.js - 添加/编辑工具对话框
 */

const AddDialog = (() => {
  let mode = 'add';      // 'add' | 'edit'
  let editId = null;
  let currentIcon = '';  // base64 或 svg: 前缀
  let iconMode = 'auto';
  let tags = [];
  let onSave = null;

  // ─── 初始化 ─────────────────────────────────────────────────────────────

  function init(saveCallback) {
    onSave = saveCallback;
    _bindEvents();
  }

  function _bindEvents() {
    const overlay = document.getElementById('add-dialog-overlay');
    if (!overlay) return;

    // 点击遮罩关闭
    overlay.addEventListener('mousedown', (e) => {
      if (e.target === overlay) close();
    });

    // 关闭按钮
    document.getElementById('add-dialog-close')
      ?.addEventListener('click', close);

    // 取消按钮
    document.getElementById('add-dialog-cancel')
      ?.addEventListener('click', close);

    // 确认保存
    document.getElementById('add-dialog-save')
      ?.addEventListener('click', _save);

    // 回车保存（非 textarea）
    overlay.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        _save();
      }
      if (e.key === 'Escape') close();
    });

    // 路径浏览按钮
    document.getElementById('btn-browse-path')
      ?.addEventListener('click', _browsePath);

    // 工作目录浏览
    document.getElementById('btn-browse-workdir')
      ?.addEventListener('click', _browseWorkdir);

    // 图标模式切换
    document.querySelectorAll('.icon-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        _setIconMode(btn.dataset.mode);
      });
    });

    // 图标图片浏览
    document.getElementById('btn-browse-icon')
      ?.addEventListener('click', _browseIcon);

    // 路径变化自动提取信息
    document.getElementById('tool-path')
      ?.addEventListener('blur', _onPathBlur);

    // 标签输入
    const tagInput = document.getElementById('tag-input-field');
    if (tagInput) {
      tagInput.addEventListener('keydown', (e) => {
        if ((e.key === 'Enter' || e.key === ',') && tagInput.value.trim()) {
          e.preventDefault();
          _addTag(tagInput.value.trim());
          tagInput.value = '';
        }
        if (e.key === 'Backspace' && !tagInput.value && tags.length > 0) {
          _removeTag(tags[tags.length - 1]);
        }
      });
    }

    document.querySelector('.tags-input-wrap')
      ?.addEventListener('click', () => tagInput?.focus());
  }

  // ─── 打开对话框 ──────────────────────────────────────────────────────────

  function open(prefill = {}) {
    mode = 'add';
    editId = null;
    currentIcon = '';
    iconMode = 'auto';
    tags = [];

    _reset();
    _prefill(prefill);
    _show();
  }

  function openEdit(tool) {
    mode = 'edit';
    editId = tool.id;
    currentIcon = tool.icon_data || '';
    iconMode = tool.icon_mode || 'auto';
    tags = Array.isArray(tool.tags) ? [...tool.tags] : [];

    _reset();
    _fillFromTool(tool);
    _show();
  }

  function _show() {
    const overlay = document.getElementById('add-dialog-overlay');
    if (!overlay) return;
    overlay.classList.remove('hidden');
    const title = document.getElementById('add-dialog-title');
    if (title) title.textContent = mode === 'edit' ? '编辑工具' : '添加工具';
    document.getElementById('tool-name')?.focus();
  }

  function close() {
    document.getElementById('add-dialog-overlay')?.classList.add('hidden');
  }

  // ─── 表单操作 ─────────────────────────────────────────────────────────────

  function _reset() {
    document.getElementById('tool-name').value       = '';
    document.getElementById('tool-path').value       = '';
    document.getElementById('tool-desc').value       = '';
    document.getElementById('tool-args').value       = '';
    document.getElementById('tool-workdir').value    = '';
    // 选第一个可用分类（动态填充，避免硬编码）
    const catSel = document.getElementById('tool-category');
    if (catSel && catSel.options.length > 0) catSel.selectedIndex = 0;
    document.getElementById('icon-text-val').value  = '';
    document.getElementById('icon-color-val').value = '#4a9eff';
    _renderIconPreview('', 'auto', '?', '#4a9eff');
    _setIconMode('auto');
    _renderTags();
  }

  function _prefill(data) {
    if (data.name)  document.getElementById('tool-name').value = data.name;
    if (data.path)  document.getElementById('tool-path').value = data.path;
    if (data.type)  document.getElementById('tool-type').value = data.type || 'file';
    if (data.icon_data) { currentIcon = data.icon_data; _renderIconPreview(currentIcon, iconMode); }
  }

  function _fillFromTool(tool) {
    document.getElementById('tool-name').value      = tool.name     || '';
    document.getElementById('tool-path').value      = tool.path     || '';
    document.getElementById('tool-desc').value      = tool.description || '';
    document.getElementById('tool-args').value      = tool.args     || '';
    document.getElementById('tool-workdir').value   = tool.work_dir || '';
    document.getElementById('tool-category').value  = tool.category || '常用';
    document.getElementById('tool-type').value      = tool.type     || 'file';
    document.getElementById('icon-text-val').value  = tool.icon_text || '';
    document.getElementById('icon-color-val').value = tool.icon_color || '#4a9eff';
    tags = Array.isArray(tool.tags) ? [...tool.tags] : [];
    _renderTags();
    _setIconMode(tool.icon_mode || 'auto');
    _renderIconPreview(currentIcon, iconMode, tool.icon_text, tool.icon_color);
  }

  // ─── 路径浏览 ─────────────────────────────────────────────────────────────

  async function _browsePath() {
    if (!window.AppBridge) return;
    const path = await window.AppBridge.openFileDialog('file');
    if (!path) return;
    document.getElementById('tool-path').value = path;
    await _autoFillFromPath(path);
  }

  async function _browseWorkdir() {
    if (!window.AppBridge) return;
    const path = await window.AppBridge.openFileDialog('folder');
    if (path) document.getElementById('tool-workdir').value = path;
  }

  async function _browseIcon() {
    if (!window.AppBridge) return;
    const path = await window.AppBridge.openFileDialog('image');
    if (!path) return;
    const icon = await window.AppBridge.extractIconSync(path);
    if (icon) {
      currentIcon = icon;
      _renderIconPreview(currentIcon, 'image');
      _setIconMode('image');
    }
  }

  async function _onPathBlur() {
    const path = document.getElementById('tool-path').value.trim();
    if (!path || mode === 'edit') return;
    await _autoFillFromPath(path);
  }

  async function _autoFillFromPath(path) {
    if (!window.AppBridge || !path) return;

    const infoStr = await window.AppBridge.getFileInfo(path);
    let info = {};
    try { info = JSON.parse(infoStr); } catch(e) {}

    // 只在名称为空时自动填充
    const nameEl = document.getElementById('tool-name');
    if (!nameEl.value.trim() && info.name) {
      nameEl.value = info.name;
    }

    const typeEl = document.getElementById('tool-type');
    if (info.type) typeEl.value = info.type;

    // 请求图标
    if (iconMode === 'auto') {
      const tmpId = '_preview';
      window.AppBridge.requestIcon(tmpId, path);
      // 监听一次结果
      _listenIconOnce(tmpId, (iconData) => {
        currentIcon = iconData;
        _renderIconPreview(currentIcon, 'auto');
      });
    }
  }

  function _listenIconOnce(id, cb) {
    const raw = window.AppBridge?._raw;
    if (!raw) return;
    const handler = (toolId, iconData) => {
      if (toolId === id) {
        raw.iconLoaded.disconnect(handler);
        cb(iconData);
      }
    };
    raw.iconLoaded.connect(handler);
  }

  // ─── 图标模式 ─────────────────────────────────────────────────────────────

  function _setIconMode(m) {
    iconMode = m;
    document.querySelectorAll('.icon-mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === m);
    });

    // 显示/隐藏相关输入组
    const autoGroup  = document.getElementById('icon-auto-group');
    const imageGroup = document.getElementById('icon-image-group');
    const textGroup  = document.getElementById('icon-text-group');

    if (autoGroup)  autoGroup.style.display  = m === 'auto'  ? ''     : 'none';
    if (imageGroup) imageGroup.style.display = m === 'image' ? ''     : 'none';
    if (textGroup)  textGroup.style.display  = m === 'text'  ? ''     : 'none';

    const name  = document.getElementById('tool-name')?.value || '?';
    const text  = document.getElementById('icon-text-val')?.value  || name.substring(0,2).toUpperCase();
    const color = document.getElementById('icon-color-val')?.value || '#4a9eff';
    _renderIconPreview(currentIcon, m, text, color);
  }

  // ─── 图标预览 ─────────────────────────────────────────────────────────────

  function _renderIconPreview(iconData, mode, text, color) {
    const previewEl = document.getElementById('icon-preview-img');
    if (!previewEl) return;

    const abbr  = text  || '?';
    const clr   = color || '#4a9eff';

    if (mode === 'text' || (!iconData && mode !== 'image')) {
      previewEl.innerHTML = `<div class="text-icon" style="background:${clr}">${abbr.substring(0,2).toUpperCase()}</div>`;
    } else if (iconData) {
      const src = iconData.startsWith('svg:')
        ? 'data:image/svg+xml;base64,' + iconData.slice(4)
        : 'data:image/png;base64,' + iconData;
      previewEl.innerHTML = `<img src="${src}" style="width:100%;height:100%;object-fit:contain;border-radius:6px">`;
    } else {
      previewEl.innerHTML = `<div class="text-icon" style="background:${clr}">${abbr.substring(0,2).toUpperCase()}</div>`;
    }
  }

  // 图标颜色/文字变更时实时预览
  document.addEventListener('input', (e) => {
    if (e.target.id === 'icon-text-val' || e.target.id === 'icon-color-val') {
      if (iconMode === 'text') {
        const text  = document.getElementById('icon-text-val')?.value || '?';
        const color = document.getElementById('icon-color-val')?.value || '#4a9eff';
        _renderIconPreview('', 'text', text, color);
      }
    }
  });

  // ─── 标签 ────────────────────────────────────────────────────────────────

  function _addTag(val) {
    if (tags.includes(val)) return;
    tags.push(val);
    _renderTags();
  }

  function _removeTag(val) {
    tags = tags.filter(t => t !== val);
    _renderTags();
  }

  function _renderTags() {
    const wrap = document.querySelector('.tags-input-wrap');
    if (!wrap) return;
    // 清除已有标签项（保留 input）
    wrap.querySelectorAll('.tag-input-item').forEach(el => el.remove());

    const field = document.getElementById('tag-input-field');
    tags.forEach(tag => {
      const chip = document.createElement('span');
      chip.className = 'tag-input-item';
      chip.innerHTML = `${_esc(tag)}<button class="tag-remove" title="删除">✕</button>`;
      chip.querySelector('.tag-remove').addEventListener('click', (e) => {
        e.stopPropagation();
        _removeTag(tag);
      });
      if (field) wrap.insertBefore(chip, field);
      else wrap.appendChild(chip);
    });
  }

  // ─── 保存 ────────────────────────────────────────────────────────────────

  async function _save() {
    const name     = document.getElementById('tool-name')?.value.trim();
    const path     = document.getElementById('tool-path')?.value.trim();
    const desc     = document.getElementById('tool-desc')?.value.trim();
    const args     = document.getElementById('tool-args')?.value.trim();
    const workDir  = document.getElementById('tool-workdir')?.value.trim();
    const category = document.getElementById('tool-category')?.value || '常用';
    const type     = document.getElementById('tool-type')?.value || 'file';
    const iconText = document.getElementById('icon-text-val')?.value.trim()
                  || name?.substring(0,2).toUpperCase() || '?';
    const iconColor= document.getElementById('icon-color-val')?.value || '#4a9eff';

    if (!name) {
      document.getElementById('tool-name')?.classList.add('anim-shake');
      setTimeout(() => document.getElementById('tool-name')?.classList.remove('anim-shake'), 400);
      return;
    }
    if (!path) {
      document.getElementById('tool-path')?.classList.add('anim-shake');
      setTimeout(() => document.getElementById('tool-path')?.classList.remove('anim-shake'), 400);
      return;
    }

    const tool = {
      name, path, description: desc, args, work_dir: workDir,
      category, type, tags,
      icon_mode: iconMode,
      icon_data: iconMode !== 'text' ? currentIcon : '',
      icon_text: iconText,
      icon_color: iconColor,
    };

    if (mode === 'edit' && editId) {
      tool.id = editId;
    }

    close();
    if (onSave) onSave(tool, mode, editId);
  }

  // ─── 工具 ────────────────────────────────────────────────────────────────

  function _esc(str) {
    return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /** 用 OS 拖拽的文件路径预填 */
  function prefillFromPaths(paths) {
    if (paths.length === 1) {
      open({ path: paths[0] });
      // 触发自动填充
      setTimeout(() => {
        const pathEl = document.getElementById('tool-path');
        if (pathEl) {
          pathEl.dispatchEvent(new Event('blur'));
        }
      }, 100);
    } else {
      // 多个文件：打开第一个，其余静默添加
      open({ path: paths[0] });
    }
  }

  return { init, open, openEdit, close, prefillFromPaths };
})();
