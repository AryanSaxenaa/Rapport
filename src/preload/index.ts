import { contextBridge, ipcRenderer } from 'electron'

const electronApi = {
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  restoreWindow: () => ipcRenderer.invoke('restore-window'),
}

contextBridge.exposeInMainWorld('electron', electronApi)

export type ElectronApi = typeof electronApi
