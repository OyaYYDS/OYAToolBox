/**
 * bridge.js - QWebChannel 初始化与桥接封装
 * 提供统一的 Python 调用接口，所有方法返回 Promise
 */

window.AppBridge = null;

function initBridge() {
  return new Promise((resolve, reject) => {
    if (typeof QWebChannel === 'undefined') {
      reject(new Error('QWebChannel 未加载'));
      return;
    }
    new QWebChannel(qt.webChannelTransport, (channel) => {
      const raw = channel.objects.bridge;
      window.AppBridge = wrapBridge(raw);
      resolve(window.AppBridge);
    });
  });
}

function wrapBridge(raw) {
  /** 将回调风格包装为 Promise */
  function call(method, ...args) {
    return new Promise((resolve) => {
      raw[method](...args, resolve);
    });
  }

  const bridge = {
    _raw: raw,

    // 工具 CRUD
    getTools:      ()           => call('getTools'),
    addTool:       (toolJson)   => call('addTool', toolJson),
    updateTool:    (id, json)   => call('updateTool', id, json),
    deleteTool:    (id)         => call('deleteTool', id),
    reorderTools:  (idsJson)    => call('reorderTools', idsJson),
    launchTool:    (id)         => call('launchTool', id),

    // 图标
    requestIcon:    (id, path) => raw.requestIcon(id, path),   // 异步信号
    extractIconSync:(path)     => call('extractIconSync', path),

    // 设置
    getSettings:   ()           => call('getSettings'),
    saveSettings:  (json)       => call('saveSettings', json),

    // 分类
    getCategories: ()           => call('getCategories'),
    addCategory:   (name)       => call('addCategory', name),
    deleteCategory:(name)       => call('deleteCategory', name),

    // 文件系统
    openFileDialog: (mode)      => call('openFileDialog', mode),
    detectFileType: (path)      => call('detectFileType', path),
    openFileLocation:(id)       => call('openFileLocation', id),
    copyPath:       (id)        => call('copyPath', id),
    getFileInfo:    (path)      => call('getFileInfo', path),

    // 窗口控制
    moveWindow:     (dx, dy)    => raw.moveWindow(dx, dy),
    resizeWindow:   (w, h)      => raw.resizeWindow(w, h),
    minimizeWindow: ()          => raw.minimizeWindow(),
    closeWindow:    ()          => raw.closeWindow(),
    setAlwaysOnTop: (on)        => raw.setAlwaysOnTop(on),

    // 信号订阅
    onToolsUpdated:    (fn) => raw.toolsUpdated.connect(fn),
    onSettingsUpdated: (fn) => raw.settingsUpdated.connect(fn),
    onIconLoaded:      (fn) => raw.iconLoaded.connect(fn),
    onFilesDropped:    (fn) => raw.filesDropped.connect(fn),
    onError:           (fn) => raw.errorOccurred.connect(fn),
  };

  return bridge;
}
