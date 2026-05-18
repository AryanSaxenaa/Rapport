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

function startPythonSidecar() {
  if (pythonProcess) return

  const sidecarDir = path.join(appRoot(), 'python-sidecar')
  const pythonCommand = process.platform === 'win32' ? 'python' : 'python3'

  pythonProcess = spawn(
    pythonCommand,
    ['-m', 'uvicorn', 'main:app', '--port', '8765', '--host', '127.0.0.1'],
    {
      cwd: sidecarDir,
      env: {
        ...process.env,
        HYDRA_DB_API_KEY: process.env.HYDRA_DB_API_KEY ?? process.env.HYDRADB_API_KEY ?? '',
        HYDRA_DB_TENANT_ID: process.env.HYDRA_DB_TENANT_ID ?? process.env.HYDRADB_TENANT_ID ?? '',
        HYDRADB_TENANT_ID: process.env.HYDRADB_TENANT_ID ?? process.env.HYDRA_DB_TENANT_ID ?? '',
        OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY ?? '',
        MY_EMAIL: process.env.MY_EMAIL ?? ''
      }
    }
  )

  pythonProcess.stdout?.on('data', (data) => {
    if (isDev) console.log(`[Python] ${data.toString()}`)
  })

  pythonProcess.stderr?.on('data', (data) => {
    if (isDev) console.warn(`[Python] ${data.toString()}`)
  })

  pythonProcess.on('exit', () => {
    pythonProcess = null
  })
}

function createWindow() {
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
      { label: 'Ingest Emails', click: () => void callSidecar('/ingest/emails', { method: 'POST' }) },
      { label: 'Open HydraDB', click: () => void shell.openExternal('https://app.hydradb.com') },
      { type: 'separator' },
      { label: 'Quit', click: () => app.quit() }
    ])
  )
}

async function callSidecar(pathname: string, init?: RequestInit) {
  const response = await fetch(`${sidecarUrl}${pathname}`, init)
  if (!response.ok) {
    throw new Error(`Sidecar ${response.status}: ${await response.text()}`)
  }
  return response.json()
}

ipcMain.handle('start-recording', async (_, contact) => {
  return callSidecar('/recording/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(contact)
  })
})

ipcMain.handle('stop-recording', async () => {
  return callSidecar('/recording/stop', { method: 'POST' })
})

ipcMain.handle('get-brief', async (_, payload: { contactEmail: string; contactName: string; company: string }) => {
  const params = new URLSearchParams({
    contact_name: payload.contactName,
    company: payload.company
  })
  return callSidecar(`/brief/${encodeURIComponent(payload.contactEmail)}?${params}`)
})

ipcMain.handle('get-contacts', async () => {
  return callSidecar('/contacts')
})

ipcMain.handle('ingest-emails', async () => {
  return callSidecar('/ingest/emails', { method: 'POST' })
})

ipcMain.on('toggle-command-bar', () => {
  mainWindow?.webContents.send('toggle-command-bar')
})

app.whenReady().then(() => {
  startPythonSidecar()
  createWindow()
  createTray()
})

app.on('window-all-closed', () => {
  mainWindow?.hide()
})

app.on('will-quit', () => {
  pythonProcess?.kill()
})
