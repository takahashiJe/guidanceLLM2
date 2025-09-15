import { registerPlugin } from '@capacitor/core';

export interface LoRaRTPlugin {
  available?: boolean;
  join(): Promise<{ value: boolean }>;
  fetch(options: { code: number; etag?: number }): Promise<null | { w:number; u:number; c:number; h?:number }>;
}

export const LoRaRT = registerPlugin<LoRaRTPlugin>('LoRaRT', {
  web: () => ({
    available: false,
    async join() { return { value: false }; },
    async fetch() { return null; },
  }),
});

export default LoRaRT;
