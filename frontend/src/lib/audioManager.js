// frontend/src/lib/audioManager.js

/**
 * @fileoverview 音声再生の管理を行うモジュール
 */

// 再生済みのスポットIDを記録するSet
// これにより、一度再生された音声が何度も再生されるのを防ぎます。
const playedSpots = new Set();

// 現在再生中のHTMLAudioElementインスタンス
let currentAudio = null;

/**
 * 指定されたスポットの音声を再生します。
 * 既に再生済みの場合は何もしません。
 * 他の音声が再生中の場合は、それを停止してから新しい音声を再生します。
 *
 * @param {object} spotInfo - 再生したいスポットの情報オブジェクト。
 * { id: string, name: string, voice_path: string } を含むことを期待します。
 */
export function playAudioForSpot(spotInfo) {
    console.debug('[AUDIO] playAudioForSpot called', spotInfo);
  // spotInfoが存在しない、またはIDがない場合は処理を中断
  if (!spotInfo || !spotInfo.id) {
    console.error("Invalid spotInfo provided to playAudioForSpot.");
    return;
  }

  // すでに再生済みのスポットであれば、コンソールにログを出力して処理を終了
  if (playedSpots.has(spotInfo.id)) {
    console.log(`Spot "${spotInfo.name}" (${spotInfo.id}) has already been played.`);
    return;
  }

  // もし別の音声が再生中であれば、再生を停止してリソースを解放
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.removeAttribute('src');
    currentAudio.load(); // バッファ解放
    currentAudio = null;
  }

  // --- 音声データの取得ロジック ---
  // voice_pathを元にローカルストレージから音声データを取得し、
  //再生可能なURL（Blob URLなど）に変換する処理を想定しています。
  // ここでは、voice_pathが直接再生可能なパスであると仮定して実装を進めます。
  // ※実際のストレージ実装に合わせてこの部分を修正してください。
  const audioPath = spotInfo.voice_path;
  if (!audioPath) {
      console.error(`No voice_path found for spot "${spotInfo.name}"`);
      return;
  }

  console.log(`Attempting to play audio for spot: "${spotInfo.name}"`);

  // 新しいAudioオブジェクトを作成
  currentAudio = new Audio(audioPath);
  console.debug('[AUDIO] new Audio created', audioPath);
  const logEv = (ev) => console.debug('[AUDIO]', ev.type, {
    readyState: currentAudio.readyState,
    networkState: currentAudio.networkState,
    error: currentAudio.error?.code
    });
    ['loadedmetadata','canplay','canplaythrough','playing','pause','stalled','suspend','abort','waiting'].forEach(
        ev => currentAudio.addEventListener(ev, logEv)
    );

  // 再生が正常に開始された場合
  currentAudio.addEventListener('play', () => {
    console.log(`Successfully started playing audio for "${spotInfo.name}".`);
    // このスポットを「再生済み」として記録
    playedSpots.add(spotInfo.id);
  });

  // 再生が終了した際のイベントリスナー
  currentAudio.addEventListener('ended', () => {
    console.log(`Finished playing audio for "${spotInfo.name}".`);
    currentAudio = null; // 再生が完了したらcurrentAudioをリセット
  });
  
  // 読み込みや再生でエラーが発生した場合
  currentAudio.addEventListener('error', (e) => {
    console.error(`Error playing audio for spot "${spotInfo.name}":`, e);
    // エラーが発生した場合でも、再試行を防ぐために再生済みとしてマークする
    // playedSpots.add(spotInfo.id); 
    const markOnError = localStorage.getItem('DEBUG_MARK_ON_ERROR') === '1';
    if (markOnError) playedSpots.add(spotInfo.id);
    currentAudio = null;
  });

  // 音声の再生を開始
  currentAudio.play().catch(error => {
      console.error(`Playback initiation failed for "${spotInfo.name}":`, error);
      console.debug('[AUDIO] Autoplay blocked?', {
        visibility: document.visibilityState,
        hasUserGesture: 'userActivation' in navigator ? navigator.userActivation.isActive : 'unknown'
    });
      // 再生開始に失敗した場合（例: ユーザー操作がない状態での自動再生制限など）
      currentAudio = null;
  });
}

/**
 * 音声の再生状態をすべてリセットします。
 * 新しいルート案内を開始する際などに呼び出すことを想定しています。
 */
export function resetPlaybackState() {
  playedSpots.clear();
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  console.log("Audio playback state has been reset.");
}