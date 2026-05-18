import { contextBridge, ipcRenderer } from 'electron'

const electronApi = {
  startRecording: (contact: unknown) => ipcRenderer.invoke('start-recording', contact),
  stopRecording: () => ipcRenderer.invoke('stop-recording'),
  getBrief: (payload: { contactEmail: string; contactName: string; company: string }) =>
    ipcRenderer.invoke('get-brief', payload),
  getContacts: () => ipcRenderer.invoke('get-contacts'),
  ingestEmails: () => ipcRenderer.invoke('ingest-emails'),
  send: (channel: 'toggle-command-bar') => ipcRenderer.send(channel),
  onToggleCommandBar: (callback: () => void) => {
    ipcRenderer.on('toggle-command-bar', callback)
    return () => {
      ipcRenderer.removeListener('toggle-command-bar', callback)
    }
  },
}

contextBridge.exposeInMainWorld('electron', electronApi)

export type ElectronApi = typeof electronApi
