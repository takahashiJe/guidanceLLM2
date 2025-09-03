<template>
  <form class="p-4 space-y-4" @submit.prevent="onSubmit">
    <div>
      <label class="block text-sm font-semibold mb-1">言語</label>
      <div class="flex gap-3">
        <label><input type="radio" value="ja" v-model="lang"> 日本語</label>
        <label><input type="radio" value="en" v-model="lang"> English</label>
        <label><input type="radio" value="zh" v-model="lang"> 中文</label>
      </div>
    </div>

    <div>
      <label class="block text-sm font-semibold mb-1">スポット順（カンマ区切りの spot_id）</label>
      <input class="w-full border rounded p-2" v-model="spotIds" placeholder="spot_001,spot_007,..." />
      <p class="text-xs text-gray-500 mt-1">後でUIをドラッグ&ドロップにしてもOK。まずはIDで。</p>
    </div>

    <div>
      <label class="block text-sm font-semibold mb-1">出発地（現在地を利用）</label>
      <button class="w-full bg-black text-white rounded py-2" type="button" @click="useCurrent">
        現在地を取得
      </button>
      <p v-if="origin" class="text-xs mt-1">lat={{origin.lat.toFixed(5)}}, lon={{origin.lon.toFixed(5)}}</p>
    </div>

    <button :disabled="!canSubmit" class="w-full bg-green-600 text-white rounded py-3">
      ルート作成
    </button>
  </form>
</template>

<script>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useNavStore } from '@/stores/nav';

export default {
  setup() {
    const nav = useNavStore();
    const router = useRouter();

    const lang = ref(nav.lang);
    const spotIds = ref('spot_001,spot_007');
    const origin = ref(null);

    async function useCurrent() {
      await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            origin.value = { lat: pos.coords.latitude, lon: pos.coords.longitude };
            resolve();
          },
          (e) => reject(e),
          { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
        );
      });
    }

    const canSubmit = computed(() => !!origin.value && !!spotIds.value);

    async function onSubmit() {
      nav.setLang(lang.value);
      nav.setWaypoints(
        spotIds.value.split(',').map(s => s.trim()).filter(Boolean)
      );
      await nav.submitPlan(origin.value);
      await nav.pollUntilReady();
      router.push({ name: 'nav' });
    }

    return { lang, spotIds, origin, canSubmit, onSubmit, useCurrent };
  }
}
</script>

<style scoped>
form { max-width: 640px; margin: 0 auto; }
</style>
