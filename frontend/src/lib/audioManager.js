// frontend/src/lib/audioManager.js

/**
 * @fileoverview 音声再生の管理（キューイング対応）を行うモジュール
 */

// --- 内部状態 ---

// 再生キュー：再生リクエストを順番に保持する配列
const playbackQueue = [];
// 再生中かどうかを示すフラグ
let isPlaying = false;
// 再生済みのユニークIDを記録するSet
const playedIds = new Set();
// 現在再生中のHTMLAudioElementインスタンス
let currentAudio = null;


/**
 * キューから次の音声を再生する内部関数。
 * 再生が終了すると、自身を再帰的に呼び出してキュー内の次のアイテムを処理します。
 */
function playNextInQueue() {
  // 再生中でない、またはキューが空の場合は処理を終了
  if (isPlaying || playbackQueue.length === 0) {
    return;
  }

  // キューの先頭から次に再生するアイテムを取得
  const spotInfo = playbackQueue.shift();
  
  // 再生済みか再チェック（キュー待機中に再生済みになるケースを考慮）
  if (playedIds.has(spotInfo.id)) {
      console.log(`[Queue] Spot "${spotInfo.name}" (${spotInfo.id}) was already played while in queue. Skipping.`);
      // すぐに次のアイテムを処理
      playNextInQueue();
      return;
  }

  const audioPath = spotInfo.voice_path;
  if (!audioPath) {
    console.error(`[Queue] No voice_path for "${spotInfo.name}". Skipping.`);
    // すぐに次のアイテムを処理
    playNextInQueue();
    return;
  }

  isPlaying = true;
  console.log(`[Queue] Playing: "${spotInfo.name}" (${spotInfo.id})`);
  
  currentAudio = new Audio(audioPath);

  // 再生開始に成功したら再生済みとして記録
  currentAudio.addEventListener('play', () => {
    playedIds.add(spotInfo.id);
  });
  
  // 再生が終了したら、状態をリセットして次のアイテムの再生を試みる
  currentAudio.addEventListener('ended', () => {
    console.log(`[Queue] Finished: "${spotInfo.name}".`);
    currentAudio = null;
    isPlaying = false;
    // 少し間を置いてから次を再生
    setTimeout(playNextInQueue, 500);
  });
  
  // エラー発生時も、次の再生に進む
  currentAudio.addEventListener('error', (e) => {
    console.error(`[Queue] Error playing "${spotInfo.name}":`, e);
    currentAudio = null;
    isPlaying = false;
    setTimeout(playNextInQueue, 500);
  });

  currentAudio.play().catch(error => {
    console.error(`[Queue] Playback initiation failed for "${spotInfo.name}":`, error);
    currentAudio = null;
    isPlaying = false;
    setTimeout(playNextInQueue, 500);
  });
}


/**
 * 指定されたスポットの音声を再生キューに追加します。
 * 既に再生済みの場合は何もしません。
 *
 * @param {object} spotInfo - 再生したいスポットの情報オブジェクト。
 * { id: string, name: string, voice_path: string } を含む必要があります。
 * `id`はspot_idとnarration_typeを組み合わせたユニークなものにしてください。
 */
export function enqueueAudio(spotInfo) {
  if (!spotInfo || !spotInfo.id || !spotInfo.voice_path) {
    console.error("[Audio] Invalid spotInfo provided to enqueueAudio.", spotInfo);
    return;
  }

  // 既に再生済みか、キューに同じIDが存在する場合は追加しない
  if (playedIds.has(spotInfo.id)) {
    console.log(`[Audio] ID "${spotInfo.id}" has already been played. Won't enqueue.`);
    return;
  }
  if (playbackQueue.some(item => item.id === spotInfo.id)) {
    console.log(`[Audio] ID "${spotInfo.id}" is already in the queue. Won't enqueue.`);
    return;
  }

  console.log(`[Audio] Enqueueing: "${spotInfo.name}" (ID: ${spotInfo.id})`);
  playbackQueue.push(spotInfo);
  
  // 現在再生中でなければ、キューの処理を開始する
  playNextInQueue();
}

/**
 * 音声の再生状態をすべてリセットします。
 * 新しいルート案内を開始する際などに呼び出します。
 */
export function resetPlaybackState() {
  playbackQueue.length = 0; // キューを空にする
  playedIds.clear();
  
  if (currentAudio) {
    // イベントリスナーをすべて削除してから停止
    currentAudio.pause();
    currentAudio.src = '';
    currentAudio = null;
  }
  
  isPlaying = false;
  console.log("[Audio] Playback state has been completely reset.");
}