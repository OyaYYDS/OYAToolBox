/**
 * bridge.js - pywebview js_api 桥接封装
 * 提供统一的 Python 调用接口 (全部返回 Promise), 方法名与旧版保持兼容
 */

window.AppBridge = null;

/**
 * 把图标数据 (data URI / svg: 前缀 / 旧版裸 base64) 统一转为 <img> 可用的 src
 */
window.iconDataToSrc = function (data) {
  if (!data) return '';
  const d = String(data);
  if (d.startsWith('data:image/') || d.startsWith('http://') || d.startsWith('https://')) {
    return d.replace(/&/g, '%26').replace(/"/g, '%22');
  }
  if (d.startsWith('svg:')) return 'data:image/svg+xml;base64,' + d.slice(4);
  return 'data:image/png;base64,' + d; // 兼容旧版裸 base64
};

function initBridge() {
  return new Promise((resolve, reject) => {
    const build = () => {
      const raw = window.pywebview && window.pywebview.api;
      if (!raw) {
        reject(new Error('pywebview api 未加载'));
        return;
      }
      window.AppBridge = wrapBridge(raw);
      resolve(window.AppBridge);
    };

    if (window.pywebview && window.pywebview.api) {
      build();
      return;
    }
    // pywebview 注入完成后触发
    window.addEventListener('pywebviewready', build, { once: true });
    // 兜底: 3 秒后仍未就绪则判定离线
    setTimeout(() => {
      if (!window.AppBridge) reject(new Error('pywebview api 未加载'));
    }, 3000);
  });
}

function wrapBridge(raw) {
  /** 事件订阅器: Python 端通过 evaluate_js 调用 _emit 推送 */
  const listeners = {
    toolsUpdated: [], settingsUpdated: [], iconLoaded: [], filesDropped: [], error: [],
  };

  function on(event, fn) {
    if (listeners[event]) listeners[event].push(fn);
  }

  function emit(event) {
    const args = Array.prototype.slice.call(arguments, 1);
    (listeners[event] || []).forEach((fn) => {
      try { fn.apply(null, args); } catch (e) { console.error(e); }
    });
  }

  return {
    _raw: raw,

    // 工具 CRUD
    getTools:      ()                  => raw.getTools(),
    addTool:       (toolJson)          => raw.addTool(toolJson),
    updateTool:    (id, json)          => raw.updateTool(id, json),
    deleteTool:    (id)                => raw.deleteTool(id),
    reorderTools:  (idsJson)           => raw.reorderTools(idsJson),
    launchTool:    (id)                => raw.launchTool(id),

    // 图标
    requestIcon:    (id, path)         => raw.requestIcon(id, path),   // 异步推送
    extractIconSync:(path)             => raw.extractIconSync(path),

    // 设置
    getSettings:   ()                  => raw.getSettings(),
    saveSettings:  (json)              => raw.saveSettings(json),

    // 分类
    getCategories: ()                  => raw.getCategories(),
    addCategory:   (name)              => raw.addCategory(name),
    deleteCategory:(name)              => raw.deleteCategory(name),

    // 文件系统
    openFileDialog: (mode)             => raw.openFileDialog(mode),
    detectFileType: (path)             => raw.detectFileType(path),
    openFileLocation:(id)              => raw.openFileLocation(id),
    copyPath:       (id)               => raw.copyPath(id),
    getFileInfo:    (path)             => raw.getFileInfo(path),

    // 窗口控制 (拖动/缩放由 pywebview 原生处理: drag region + frameless 边缘缩放)
    minimizeWindow: ()                 => raw.minimizeWindow(),
    closeWindow:    ()                 => raw.closeWindow(),
    setAlwaysOnTop: (on)               => raw.setAlwaysOnTop(on),

    // 信号订阅
    onToolsUpdated:    (fn)            => on('toolsUpdated', fn),
    onSettingsUpdated: (fn)            => on('settingsUpdated', fn),
    onIconLoaded:      (fn)            => on('iconLoaded', fn),
    onFilesDropped:    (fn)            => on('filesDropped', fn),
    onError:           (fn)            => on('error', fn),

    // 供 Python evaluate_js 调用
    _emit: emit,
  };
}
