import { defineStore } from "pinia";

export const useNavStore = defineStore("nav", {
  state: () => ({
    currentLegIdx: 0,
    triggeredSpotIds: new Set(),
    playback: { nowPlayingSpotId: null },
  }),
  actions: {
    markTriggered(spotId) {
      this.triggeredSpotIds.add(spotId);
    },
    setNowPlaying(spotId) {
      this.playback.nowPlayingSpotId = spotId;
    },
    reset() {
      this.currentLegIdx = 0;
      this.triggeredSpotIds = new Set();
      this.playback = { nowPlayingSpotId: null };
    },
  },
});
