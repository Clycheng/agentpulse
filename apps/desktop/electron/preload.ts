import { contextBridge } from 'electron';

contextBridge.exposeInMainWorld('agentpulse', {
  platform: process.platform,
});
