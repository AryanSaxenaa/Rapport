import { contextBridge, ipcRenderer } from 'electron'

const electronApi = {
  startRecording: (contact: unknown) => ipcRenderer.invoke('start-recording', contact),
  stopRecording: () => ipcRenderer.invoke('stop-recording'),
  getBrief: (payload: { contactEmail: string; contactName: string; company: string }) =>
    ipcRenderer.invoke('get-brief', payload),
  getContacts: () => ipcRenderer.invoke('get-contacts'),
  ingestEmails: () => ipcRenderer.invoke('ingest-emails'),
  // App minimize/restore is handled client-side in FloatingOrb
}

contextBridge.exposeInMainWorld('electron', electronApi)

export type ElectronApi = typeof electronApi
