import { defineStore } from "pinia";

export const useGeoStore = defineStore("geo", {
  state: () => ({
    position: null, // { lat, lon, accuracy, speed, heading }
    watchId: null,
    error: null,
  }),
  actions: {
    startWatch(options = { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }) {
      if (!("geolocation" in navigator)) {
        this.error = "Geolocation unsupported";
        return;
      }
      if (this.watchId) navigator.geolocation.clearWatch(this.watchId);
      this.watchId = navigator.geolocation.watchPosition(
        (pos) => {
          const c = pos.coords;
          this.position = {
            lat: c.latitude,
            lon: c.longitude,
            accuracy: c.accuracy,
            speed: c.speed,
            heading: c.heading,
          };
          this.error = null;
        },
        (err) => {
          this.error = err?.message || String(err);
        },
        options
      );
    },
    stopWatch() {
      if (this.watchId) navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
    },
  },
});
