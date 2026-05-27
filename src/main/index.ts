import { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, screen, shell } from 'electron'
import { spawn, type ChildProcess } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let pythonProcess: ChildProcess | null = null

const isDev = process.env.NODE_ENV === 'development'
const sidecarUrl = 'http://127.0.0.1:8765'

function appRoot() {
  return isDev ? process.cwd() : app.getAppPath()
}

async function isSidecarHealthy() {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 1200)
  try {
    const response = await fetch(`${sidecarUrl}/health`, { signal: controller.signal })
    return response.ok
  } catch {
    return false
  } finally {
    clearTimeout(timeout)
  }
}

async function startPythonSidecar() {
  if (pythonProcess) return
  if (await isSidecarHealthy()) {
    if (isDev) console.log('[Python] Reusing existing sidecar on 127.0.0.1:8765')
    return
  }

  const root = appRoot()
  let cmd: string
  let args: string[]

  // Production: use PyInstaller binary if present
  const binaryName = process.platform === 'win32' ? 'rapport-sidecar.exe' : 'rapport-sidecar'
  const bundledBinary = path.join(root, 'python-sidecar', 'dist', 'rapport-sidecar', binaryName)
  const binaryExists = await import('node:fs').then((fs) => fs.existsSync(bundledBinary))

  if (!isDev && binaryExists) {
    cmd = bundledBinary
    args = ['--port', '8765', '--host', '127.0.0.1']
  } else {
    const pythonCommand = process.platform === 'win32' ? 'python' : 'python3'
    cmd = pythonCommand
    args = ['-m', 'uvicorn', 'main:app', '--port', '8765', '--host', '127.0.0.1']
  }

  pythonProcess = spawn(cmd, args, {
    cwd: path.join(root, 'python-sidecar'),
    env: {
      ...process.env,
      HYDRA_DB_API_KEY: process.env.HYDRA_DB_API_KEY ?? '',
      HYDRA_DB_TENANT_ID: process.env.HYDRA_DB_TENANT_ID ?? '',
      OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY ?? '',
      MY_EMAIL: process.env.MY_EMAIL ?? ''
    }
  })

  pythonProcess.stdout?.on('data', (data) => {
    if (isDev) console.log(`[Python] ${data.toString()}`)
  })

  pythonProcess.stderr?.on('data', (data) => {
    if (isDev) console.warn(`[Python] ${data.toString()}`)
  })

  pythonProcess.on('exit', (code) => {
    pythonProcess = null
    // BUG-19: Restart the sidecar automatically after a non-zero exit so
    // the UI doesn't stay permanently offline after a transient crash.
    if (code !== 0 && code !== null) {
      if (isDev) console.warn(`[Python] sidecar exited with code ${code} — restarting in 3 s`)
      setTimeout(() => void startPythonSidecar(), 3000)
    }
  })
}

function createWindow() {
  // BUG-18: Reset the pre-minimize position whenever a new window is created
  // so a stale value from a previous window can't mis-position this one.
  windowBeforeMinimize = null

  mainWindow = new BrowserWindow({
    width: 460,
    height: 720,
    minWidth: 360,
    minHeight: 560,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    skipTaskbar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  mainWindow.setPosition(Math.max(width - 500, 0), Math.max(height - 760, 0))

  mainWindow.once('ready-to-show', () => mainWindow?.show())

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }
}

function createTray() {
  const image = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAIklEQVR4AWP4TyFgGEY0AhyG/6H4Tw0jGgGOYRBmAQDsrAgR3FeJ9QAAAABJRU5ErkJggg=='
  )
  tray = new Tray(image)
  tray.setToolTip('Rapport')
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: 'Show Rapport', click: () => mainWindow?.show() },
      { label: 'Open HydraDB', click: () => void shell.openExternal('https://app.hydradb.com') },
      { type: 'separator' },
      { label: 'Quit', click: () => app.quit() }
    ])
  )
}

let windowBeforeMinimize: { x: number; y: number } | null = null

ipcMain.handle('minimize-window', () => {
  if (!mainWindow) return
  if (windowBeforeMinimize) return
  const bounds = mainWindow.getBounds()
  const orbSize = 100
  windowBeforeMinimize = { x: bounds.x, y: bounds.y }
  mainWindow.setBounds({ x: bounds.x + bounds.width - orbSize, y: bounds.y, width: orbSize, height: orbSize }, true)
})

ipcMain.handle('restore-window', () => {
  if (!mainWindow) return
  const pos = windowBeforeMinimize ?? { x: 0, y: 0 }
  windowBeforeMinimize = null
  mainWindow.setBounds({ x: pos.x, y: pos.y, width: 460, height: 720 }, true)
})

app.whenReady().then(async () => {
  await startPythonSidecar()
  createWindow()
  createTray()

  // Auto-update: only runs in production with electron-updater installed
  if (!isDev) {
    try {
      // @ts-ignore - electron-updater is an optional dependency injected during official builds
      const { autoUpdater } = await import('electron-updater')
      autoUpdater.checkForUpdatesAndNotify().catch(() => {/* no network or no release */})
    } catch {
      // electron-updater not installed — skip silently
    }
  }
})

app.on('window-all-closed', () => {
  mainWindow?.hide()
})

app.on('will-quit', () => {
  pythonProcess?.kill()
})

