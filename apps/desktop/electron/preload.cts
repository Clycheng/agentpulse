import { contextBridge, ipcRenderer } from 'electron';

type SessionPayload = {
  accessToken: string;
  user: { id: string; email: string; display_name: string };
};

contextBridge.exposeInMainWorld('agentpulse', {
  platform: process.platform,
  session: {
    get: () => ipcRenderer.invoke('agentpulse:session:get'),
    set: (value: SessionPayload) =>
      ipcRenderer.invoke('agentpulse:session:set', value),
    clear: () => ipcRenderer.invoke('agentpulse:session:clear'),
  },
});
