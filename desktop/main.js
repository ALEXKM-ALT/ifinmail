const { app, BrowserWindow, Tray, Menu, Notification, shell, dialog, nativeImage, ipcMain, nativeTheme } = require("electron");
const path = require("path");
const fs = require("fs");
const { autoUpdater } = require("electron-updater");

const isDev = process.env.ELECTRON_DEV === "1" || !app.isPackaged;
const DEV_URL = "http://localhost:8000";
const APP_NAME = "ifinmail";

if (process.argv.includes("--no-sandbox")) {
  app.commandLine.appendSwitch("no-sandbox");
}
app.commandLine.appendSwitch("disable-gpu");
app.commandLine.appendSwitch("disable-software-rasterizer");

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", (_, argv) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
    const mailto = argv.find(a => a.startsWith("mailto:"));
    if (mailto && mainWindow) {
      mainWindow.webContents.send("navigate", `/compose?mailto=${encodeURIComponent(mailto)}`);
    }
  });
}

let mainWindow = null;
let tray = null;
let isQuitting = false;

const STATIC_DIR = path.join(__dirname, "..", "src", "ifinmail", "web", "static");

const CONFIG_PATH = path.join(app.getPath("userData"), "window-state.json");

function loadWindowState() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
    }
  } catch {}
  return { width: 1200, height: 800, x: undefined, y: undefined, maximized: false };
}

function saveWindowState() {
  if (!mainWindow) return;
  try {
    const isMax = mainWindow.isMaximized();
    if (!isMax) {
      const bounds = mainWindow.getBounds();
      fs.writeFileSync(CONFIG_PATH, JSON.stringify({ ...bounds, maximized: false }));
    } else {
      const prev = loadWindowState();
      fs.writeFileSync(CONFIG_PATH, JSON.stringify({ ...prev, maximized: true }));
    }
  } catch {}
}

function loadPref(key, def) {
  try {
    const p = path.join(app.getPath("userData"), "prefs.json");
    if (fs.existsSync(p)) {
      const prefs = JSON.parse(fs.readFileSync(p, "utf-8"));
      return prefs[key] !== undefined ? prefs[key] : def;
    }
  } catch {}
  return def;
}

function savePref(key, value) {
  try {
    const p = path.join(app.getPath("userData"), "prefs.json");
    const prefs = fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf-8")) : {};
    prefs[key] = value;
    fs.writeFileSync(p, JSON.stringify(prefs, null, 2));
  } catch {}
}

function getIcon(name = "icon.png") {
  const p = path.join(__dirname, "assets", name);
  return fs.existsSync(p) ? p : null;
}

function createTray() {
  const iconPath = getIcon();
  if (!iconPath) return;
  const icon = nativeImage.createFromPath(iconPath);
  tray = new Tray(icon.resize({ width: 16, height: 16 }));
  tray.setToolTip(APP_NAME);

  const autoStart = app.getLoginItemSettings().openAtLogin;
  const ctx = Menu.buildFromTemplate([
    { label: "Open ifinmail", click: () => mainWindow?.show() },
    { type: "separator" },
    {
      label: `Launch at startup${autoStart ? " ✓" : ""}`,
      click: (item) => {
        const newVal = !app.getLoginItemSettings().openAtLogin;
        app.setLoginItemSettings({ openAtLogin: newVal });
        createTray();
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => { isQuitting = true; app.quit(); },
    },
  ]);
  tray.setContextMenu(ctx);
  tray.on("double-click", () => mainWindow?.show());
}

function createMenu() {
  const template = [
    {
      label: APP_NAME,
      submenu: [
        {
          label: `About ${APP_NAME}`,
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: "info",
              title: `About ${APP_NAME}`,
              message: `${APP_NAME} Desktop v${app.getVersion()}`,
              detail: `A secure, API-first email client.\nPlatform: ${process.platform} (${process.arch})\nElectron: ${process.versions.electron}\nChrome: ${process.versions.chrome}\nNode.js: ${process.versions.node}`,
              icon: getIcon(),
            });
          },
        },
        { type: "separator" },
        {
          label: "Preferences",
          accelerator: "CmdOrCtrl+,",
          click: () => mainWindow?.webContents.send("navigate", "/settings"),
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { type: "separator" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    {
      label: "Mailbox",
      submenu: [
        {
          label: "Compose New Message",
          accelerator: "CmdOrCtrl+N",
          click: () => mainWindow?.webContents.send("navigate", "/compose"),
        },
        {
          label: "Refresh",
          accelerator: "CmdOrCtrl+R",
          click: () => mainWindow?.webContents.send("refresh"),
        },
        { type: "separator" },
        {
          label: "Go to Inbox",
          accelerator: "CmdOrCtrl+Shift+I",
          click: () => mainWindow?.webContents.send("navigate", "/mail"),
        },
      ],
    },
    {
      label: "Window",
      submenu: [
        { role: "minimize" },
        { role: "close" },
      ],
    },
    {
      label: "Help",
      submenu: [
        {
          label: "ifinmail Documentation",
          click: () => shell.openExternal("https://ifinmail.com/docs"),
        },
        { type: "separator" },
        { role: "toggleDevTools" },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  const state = loadWindowState();

  mainWindow = new BrowserWindow({
    width: state.width,
    height: state.height,
    x: state.x,
    y: state.y,
    minWidth: 800,
    minHeight: 600,
    title: APP_NAME,
    icon: getIcon(),
    show: false,
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#0f172a" : "#ffffff",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      spellcheck: true,
    },
  });

  const zoom = loadPref("zoom", 1.0);
  mainWindow.webContents.setZoomFactor(zoom);

  mainWindow.loadURL(DEV_URL);

  if (state.maximized) mainWindow.maximize();
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    if (!isDev) autoUpdater.checkForUpdatesAndNotify();
  });

  mainWindow.on("close", (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on("resize", saveWindowState);
  mainWindow.on("move", saveWindowState);
  mainWindow.on("maximize", saveWindowState);
  mainWindow.on("unmaximize", saveWindowState);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://localhost:8000") || url.startsWith("http://127.0.0.1:8000")) {
      return { action: "allow" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith("http://localhost:8000") && !url.startsWith("http://127.0.0.1:8000")) {
      e.preventDefault();
      shell.openExternal(url);
    }
  });

  mainWindow.webContents.on("context-menu", (e, params) => {
    const isEditable = params.isEditable;
    const hasSelection = params.selectionText?.length > 0;
    const isLink = !!params.linkURL;
    const isImage = !!params.mediaType && params.mediaType.startsWith("image");

    const ctx = [];

    if (isLink) {
      ctx.push(
        { label: "Open link", click: () => shell.openExternal(params.linkURL) },
        { label: "Copy link address", click: () => mainWindow?.webContents.copyImageAt(params.x, params.y) },
      );
    }

    if (isImage) {
      ctx.push(
        { label: "Save image", click: () => mainWindow?.webContents.downloadURL(params.srcURL) },
      );
    }

    if (ctx.length && (isEditable || hasSelection)) ctx.push({ type: "separator" });

    if (isEditable) {
      ctx.push(
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      );
    } else if (hasSelection) {
      ctx.push({ role: "copy" });
    }

    if (isEditable) {
      ctx.push({ type: "separator" });
      ctx.push({ role: "spellCheck" });
    }

    if (ctx.length) {
      Menu.buildFromTemplate(ctx).popup({ window: mainWindow });
    }
  });
}

function setupIPC() {
  ipcMain.handle("get-app-version", () => app.getVersion());
  ipcMain.handle("get-platform", () => process.platform);
  ipcMain.handle("get-data-path", () => app.getPath("userData"));

  ipcMain.handle("show-save-dialog", async (_, opts) => {
    const result = await dialog.showSaveDialog(mainWindow, opts);
    return result;
  });

  ipcMain.handle("show-open-dialog", async (_, opts) => {
    const result = await dialog.showOpenDialog(mainWindow, opts);
    return result;
  });

  ipcMain.handle("show-notification", (_, { title, body }) => {
    if (!loadPref("notifications", true)) return;
    if (Notification.isSupported()) {
      const n = new Notification({ title, body, icon: getIcon() });
      n.on("click", () => mainWindow?.show());
      n.show();
    }
  });

  ipcMain.handle("set-badge", (_, count) => {
    if (process.platform === "darwin" || process.platform === "linux") {
      app.setBadgeCount?.(count);
    }
  });

  ipcMain.handle("write-file", async (_, filePath, data) => {
    try {
      fs.writeFileSync(filePath, Buffer.from(data));
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle("read-file", async (_, filePath) => {
    try {
      const data = fs.readFileSync(filePath);
      return { success: true, data: data.buffer ? Array.from(data) : data };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle("get-api-url", () => DEV_URL);

  ipcMain.handle("get-pref", (_, key, def) => loadPref(key, def));
  ipcMain.handle("set-pref", (_, key, value) => { savePref(key, value); });

  ipcMain.handle("set-zoom", (_, factor) => {
    mainWindow?.webContents.setZoomFactor(factor);
    savePref("zoom", factor);
  });

  ipcMain.handle("get-zoom", () => mainWindow?.webContents.getZoomFactor() || 1.0);

  ipcMain.handle("is-dark-mode", () => nativeTheme.shouldUseDarkColors);
  ipcMain.handle("set-auto-start", (_, enable) => {
    app.setLoginItemSettings({ openAtLogin: enable });
  });
  ipcMain.handle("get-auto-start", () => app.getLoginItemSettings().openAtLogin);

  ipcMain.handle("open-external", (_, url) => {
    shell.openExternal(url);
  });

  ipcMain.handle("show-message-context-menu", (event, msg) => {
    const ctx = Menu.buildFromTemplate([
      { label: "Reply", click: () => event.sender.send("message-context-action", "reply") },
      { label: "Reply All", click: () => event.sender.send("message-context-action", "reply-all") },
      { label: "Forward", click: () => event.sender.send("message-context-action", "forward") },
      { type: "separator" },
      { label: msg.read ? "Mark unread" : "Mark read", click: () => event.sender.send("message-context-action", "toggle-read") },
      { label: "Archive", click: () => event.sender.send("message-context-action", "archive") },
      { label: "Delete", click: () => event.sender.send("message-context-action", "delete") },
      { type: "separator" },
      { label: "Star / unstar", click: () => event.sender.send("message-context-action", "star") },
    ]);
    ctx.popup({ window: mainWindow });
  });
}

function setupAutoUpdater() {
  autoUpdater.autoDownload = false;
  autoUpdater.setFeedURL({
    provider: "github",
    repo: "ifinmail",
    owner: "ifinsta",
  });

  autoUpdater.on("update-available", (info) => {
    dialog.showMessageBox(mainWindow, {
      type: "info",
      title: "Update Available",
      message: `Version ${info.version} is available. Download now?`,
      buttons: ["Download", "Later"],
    }).then(({ response }) => {
      if (response === 0) autoUpdater.downloadUpdate();
    });
  });

  autoUpdater.on("update-downloaded", () => {
    dialog.showMessageBox(mainWindow, {
      type: "info",
      title: "Update Ready",
      message: "Restart to install the update?",
      buttons: ["Restart", "Later"],
    }).then(({ response }) => {
      if (response === 0) autoUpdater.quitAndInstall();
    });
  });

  autoUpdater.on("error", () => {});
}

app.whenReady().then(() => {
  app.setAsDefaultProtocolClient("mailto");
  createMenu();
  createWindow();
  setupIPC();
  setupAutoUpdater();

  nativeTheme.on("updated", () => {
    mainWindow?.webContents.send("theme-changed", nativeTheme.shouldUseDarkColors);
    mainWindow?.setBackgroundColor(nativeTheme.shouldUseDarkColors ? "#0f172a" : "#ffffff");
  });

  const mailto = process.argv.find(a => a.startsWith("mailto:"));
  if (mailto) {
    mainWindow?.webContents.once("did-finish-load", () => {
      mainWindow?.webContents.send("navigate", `/compose?mailto=${encodeURIComponent(mailto)}`);
    });
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else mainWindow?.show();
  });

  createTray();

  app.setAppUserModelId?.("com.ifinmail.desktop");
});

app.on("before-quit", () => {
  isQuitting = true;
  saveWindowState();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
