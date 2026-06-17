const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ifinmail", {
  platform: process.platform,
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron,
  },

  getAppVersion: () => ipcRenderer.invoke("get-app-version"),
  getPlatform: () => ipcRenderer.invoke("get-platform"),
  getDataPath: () => ipcRenderer.invoke("get-data-path"),
  getApiUrl: () => ipcRenderer.invoke("get-api-url"),
  isDarkMode: () => ipcRenderer.invoke("is-dark-mode"),
  setAutoStart: (enable) => ipcRenderer.invoke("set-auto-start", enable),
  getAutoStart: () => ipcRenderer.invoke("get-auto-start"),

  getPref: (key, def) => ipcRenderer.invoke("get-pref", key, def),
  setPref: (key, value) => ipcRenderer.invoke("set-pref", key, value),
  setZoom: (factor) => ipcRenderer.invoke("set-zoom", factor),
  getZoom: () => ipcRenderer.invoke("get-zoom"),

  showSaveDialog: (opts) => ipcRenderer.invoke("show-save-dialog", opts),
  showOpenDialog: (opts) => ipcRenderer.invoke("show-open-dialog", opts),
  showNotification: (opts) => ipcRenderer.invoke("show-notification", opts),
  setBadge: (count) => ipcRenderer.invoke("set-badge", count),

  writeFile: (path, data) => ipcRenderer.invoke("write-file", path, data),
  readFile: (path) => ipcRenderer.invoke("read-file", path),

  onNavigate: (callback) => {
    ipcRenderer.on("navigate", (_, route) => callback(route));
    return () => ipcRenderer.removeAllListeners("navigate");
  },

  onRefresh: (callback) => {
    ipcRenderer.on("refresh", () => callback());
    return () => ipcRenderer.removeAllListeners("refresh");
  },

  onThemeChanged: (callback) => {
    ipcRenderer.on("theme-changed", (_, isDark) => callback(isDark));
    return () => ipcRenderer.removeAllListeners("theme-changed");
  },

  openExternal: (url) => ipcRenderer.invoke("open-external", url),

  showMessageContextMenu: (msg) => ipcRenderer.invoke("show-message-context-menu", msg),
  onMessageContextAction: (callback) => {
    const handler = (_, action) => callback(action);
    ipcRenderer.on("message-context-action", handler);
    return () => ipcRenderer.removeListener("message-context-action", handler);
  },
});
