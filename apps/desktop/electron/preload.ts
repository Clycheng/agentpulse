import { contextBridge } from 'electron';

contextBridge.exposeInMainWorld('intentpulse', {
  platform: process.platform,
});
