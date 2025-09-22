let port = null;
let reader = null;
let writer = null;

let isJoinCommandActive = false;
let joinPromise = {};

let _isPortConnected = false;
let _isNetworkJoined = false;

let onDataReceived = () => {};
let onDisconnected = () => {};

/**
 * シリアルポートからのすべてのデータを一括で処理する単一の読み取りループ
 */
async function readLoop() {
  if (!reader) return;
  console.log('[LoRa] 読み取りループを開始します。');
  
  // ★★★★★ 解決策1: 受信データを溜めるバッファ ★★★★★
  let lineBuffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        // リーダーが解放されたらループを抜ける
        reader.releaseLock();
        break;
      }
      
      // バッファに受信データを追加
      lineBuffer += value;
      
      // ★★★★★ バッファを改行コードで分割し、行ごとに処理 ★★★★★
      let lines = lineBuffer.split(/\r?\n/);
      // 最後の要素は次の受信データと結合するため、バッファに残す
      lineBuffer = lines.pop();

      for (const line of lines) {
        const fullResponse = line.trim();
        if (fullResponse === '') continue; // 空行は無視
        
        console.log(`[LoRa MSG] 受信:`, fullResponse);

        // --- Joinコマンド応答の処理 ---
        if (isJoinCommandActive) {
          if (fullResponse.includes('JOINED') || fullResponse.includes('+JOIN: OK')) {
            console.log("LoRaWAN参加成功！");
            _isNetworkJoined = true;
            isJoinCommandActive = false;
            if (joinPromise.resolve) joinPromise.resolve(true);
          } else if (fullResponse.includes('Failed') || fullResponse.includes('AT_ERROR')) {
            // AT_ERRORは他のコマンドでも返るため、Join中のみ失敗と判断
            console.error("LoRaWAN参加失敗");
            _isNetworkJoined = false;
            isJoinCommandActive = false;
            if (joinPromise.reject) joinPromise.reject(new Error('LoRaWAN Join Failed'));
          }
        }
        
        // --- ダウンリンクデータの処理 ---
        if (fullResponse.startsWith('+RECV:')) {
          console.log(`ダウンリンク受信: ${fullResponse}`);
          try {
            const parts = fullResponse.split(',');
            if (parts.length >= 3) {
              const hexData = parts[2].trim();
              const jsonData = hexToString(hexData);
              onDataReceived(JSON.parse(jsonData));
            }
          } catch (e) {
            console.error('受信データのパースに失敗:', e, {fullResponse});
          }
        }

        // --- 切断（リブート）検知 ---
        if (fullResponse.includes('Dragino OTA bootloader')) {
          console.warn('[LoRa] デバイスがリブートしました。接続状態をリセットします。');
          _isNetworkJoined = false;
          if (onDisconnected) onDisconnected();
        }
      }
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      console.error('読み取りループでエラーが発生しました:', error);
    }
  }
  console.log('[LoRa] 読み取りループが停止しました。');
}

export async function connect(onData, onDisconnectCb) {
  if (_isPortConnected) return true;
  if (!navigator.serial) {
    alert('お使いのブラウザはWeb Serial APIをサポートしていません。');
    return false;
  }
  try {
    port = await navigator.serial.requestPort();
    await port.open({ baudRate: 9600 });

    onDataReceived = onData;
    onDisconnected = onDisconnectCb;

    const textEncoder = new TextEncoderStream();
    writer = textEncoder.writable.getWriter();
    textEncoder.readable.pipeTo(port.writable);
    
    const textDecoder = new TextDecoderStream();
    // ★★★★★ 解決策2: pipeThroughでストリームを安全に処理 ★★★★★
    const readableStream = port.readable.pipeThrough(textDecoder);
    reader = readableStream.getReader();
    
    _isPortConnected = true;
    _isNetworkJoined = false;
    
    readLoop(); // 読み取りループを開始

    console.log('シリアルポートに接続しました。');
    return true;
  } catch (error) {
    console.error('シリアルポートへの接続に失敗しました:', error);
    return false;
  }
}

export async function disconnect() {
  // ★★★★★ 解決策2: 安全な切断処理 ★★★★★
  if (reader) {
    try {
      await reader.cancel(); // 進行中のreadをキャンセル
      // releaseLock() はreadLoopのdoneフラグで自動的に呼ばれる
    } catch(e) {
      console.error('リーダーのキャンセルに失敗:', e);
    }
    reader = null;
  }
  if (writer) {
    try {
      if (!writer.closed) {
         await writer.close();
      }
    } catch(e) {
       console.error('ライターのクローズに失敗:', e);
    }
    writer = null;
  }
  if (port && port.close) {
    try {
      await port.close();
    } catch(e) {
      console.error('ポートのクローズに失敗:', e);
    }
    port = null;
  }
  _isPortConnected = false;
  _isNetworkJoined = false;
  console.log('シリアルポートを切断しました。');
}


export function join() { // asyncを外してPromiseを直接返す
  if (!_isPortConnected || !writer) {
    return Promise.reject(new Error('Port not ready'));
  }
  if (isJoinCommandActive) {
      return Promise.reject(new Error('Join in progress'));
  }
  
  isJoinCommandActive = true;
  _isNetworkJoined = false;
  
  // コマンド送信は非同期で行う
  const sendCommands = async () => {
    try {
      const commands = [
        'ATZ',
        'AT+MODE=LWOTAA',
        'AT+DEVEUI=A8404168E189621F',
        'AT+APPEUI=A840410000000101',
        'AT+APPKEY=138F1A42A61329A3918FC834BCAD0071',
        'AT+SAVE'
      ];
      for (const cmd of commands) {
        await writer.write(`${cmd}\r\n`);
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      await writer.write('AT+JOIN\r\n');
      console.log('ネットワークに参加します... (AT+JOIN)');
    } catch (e) {
        isJoinCommandActive = false;
        if(joinPromise.reject) joinPromise.reject(e);
    }
  };
  
  sendCommands();

  return new Promise((resolve, reject) => {
    joinPromise = { resolve, reject };
    setTimeout(() => {
      if (isJoinCommandActive) {
        isJoinCommandActive = false;
        reject(new Error('Join command timed out'));
      }
    }, 30000);
  });
}

export function getIsJoined() {
  return _isNetworkJoined;
}

export async function send(data) {
  if (!writer || !_isNetworkJoined) {
    console.warn('LoRa未接続のため送信をスキップしました。');
    return;
  }
  const hexData = Array.from(new TextEncoder().encode(data))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  
  const command = `AT+SEND=2:${hexData}`;
  console.log(`データ送信: ${command}`);
  await writer.write(`${command}\r\n`);
}

function hexToString(hex) {
  let str = '';
  for (let i = 0; i < hex.length; i += 2) {
      str += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
  }
  return str;
}