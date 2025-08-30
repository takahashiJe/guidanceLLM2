import { defineStore } from "pinia";

export const useSettingsStore = defineStore("settings", {
  state: () => ({
    lang: "ja",
    ttsRate: 1.0,
    powerSave: false,
  }),
  actions: {
    setLang(l) { this.lang = l; },
    setRate(r) { this.ttsRate = r; },
    setPowerSave(v) { this.powerSave = v; },
  },
});
