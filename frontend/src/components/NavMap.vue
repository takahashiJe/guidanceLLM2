<!-- src/components/NavMap.vue -->
<template>
  <div ref="mapEl" class="w-full h-full"></div>
</template>

<script>
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default {
  name: 'NavMap',
  props: {
    plan: { type: Object, default: null },
  },
  setup(props) {
    const mapEl = ref(null)
    let map, routeLayer, marker

    function ensureMap() {
      if (map) return
      map = L.map(mapEl.value)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '&copy; OpenStreetMap'
      }).addTo(map)
      routeLayer = L.geoJSON().addTo(map)
      marker = L.circleMarker([39.22, 139.90], { radius: 6 }).addTo(map)
      map.setView([39.22, 139.90], 11)
    }

    function drawPlan() {
      if (!map || !props.plan?.route) return
      routeLayer.clearLayers()
      routeLayer.addData(props.plan.route)
      try {
        map.fitBounds(routeLayer.getBounds(), { padding: [20, 20] })
      } catch(_) {}
    }

    // 現在地を更新（ナビ用途）
    function updateCurrentPosition() {
      if (!navigator.geolocation) return
      navigator.geolocation.getCurrentPosition((pos) => {
        const { latitude, longitude } = pos.coords
        marker.setLatLng([latitude, longitude])
      })
    }

    onMounted(() => {
      ensureMap()
      drawPlan()
      updateCurrentPosition()
      // ゆるく現在地更新
      const id = setInterval(updateCurrentPosition, 5000)
      onUnmounted(() => clearInterval(id))
    })

    watch(() => props.plan, drawPlan, { deep: true })

    return { mapEl }
  }
}
</script>

<style scoped>
/* 端末全画面で見やすいように */
:host, .w-full.h-full, div[ref="mapEl"] { height: 100%; }
</style>
