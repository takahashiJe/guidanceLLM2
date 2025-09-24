import { ref } from 'vue';
import { useNavStore } from '@/stores/nav';

// デバッグ用: 位置情報を手動で操作する
export function usePosition() {
  const navStore = useNavStore();
  const currentPos = ref(null);

  const moveToTestSpot = () => {
    const plan = navStore.plan;
    if (!plan?.waypoints_info?.[0]) {
      alert('テスト用のスポットが見つかりません。');
      return;
    }
    const testSpot = plan.waypoints_info[0];

    currentPos.value = {
      lat: testSpot.lat + 0.0001,
      lng: testSpot.lon + 0.0001,
    };
    console.log('デバッグ：位置を更新しました', currentPos.value);
  };

  return {
    currentPos,
    moveToTestSpot, // デバッグ用の関数を返す
  };
}