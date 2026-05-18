import { contextBridge, ipcRenderer } from 'electron'

const electronApi = {
  startRecording: (contact: unknown) => ipcRenderer.invoke('start-recording', contact),
  stopRecording: () => ipcRenderer.invoke('stop-recording'),
  getBrief: (payload: { contactEmail: string; contactName: string; company: string }) =>
    ipcRenderer.invoke('get-brief', payload),
  getContacts: () => ipcRenderer.invoke('get-contacts'),
  ingestEmails: () => ipcRenderer.invoke('ingest-emails'),
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  restoreWindow: () => ipcRenderer.invoke('restore-window'),
}

contextBridge.exposeInMainWorld('electron', electronApi)

export type ElectronApi = typeof electronApi
