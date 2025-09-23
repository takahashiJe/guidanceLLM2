let port = null;
let reader = null;
let writer = null;
let readableStreamClosed = null;

// --- 内部状態フラグ ---
let _isPortConnected = false;
let _isNetworkJoined = false;
let isInitializing = false; 
let isJoinCommandActive = false;
let joinPromise = {};

// --- コールバック関数 ---
let onDataReceived = () => {};
let onDisconnected = () => {};

async function readLoop() {
  if (!reader) return;
  console.log('[LoRa] 読み取りループを開始します。');
  let lineBuffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      
      lineBuffer += value;
      let lines = lineBuffer.split(/\r?\n/);
      lineBuffer = lines.pop();

      for (const line of lines) {
        const fullResponse = line.trim();
        if (fullResponse === '') continue;
        document.dispatchEvent(new CustomEvent('lora-line-received', { detail: fullResponse }));
        console.log(`[LoRa MSG] 受信:`, fullResponse);

        if (isJoinCommandActive) {
          if (fullResponse.includes('JOINED') || fullResponse.includes('+JOIN: OK')) {
            console.log("LoRaWAN参加成功！");
            _isNetworkJoined = true;
            isJoinCommandActive = false;
            if (joinPromise.resolve) joinPromise.resolve(true);
          } else if (fullResponse.includes('+JOIN: Failed')) { 
            console.error("LoRaWAN参加失敗");
            _isNetworkJoined = false;
            isJoinCommandActive = false;
            if (joinPromise.reject) joinPromise.reject(new Error('LoRaWAN Join Failed'));
          } else if (fullResponse.includes('AT_ERROR') && Date.now() - joinPromise.startTime > 3000) {
             console.error("LoRaWAN参加中にエラーを検知");
            _isNetworkJoined = false;
            isJoinCommandActive = false;
            if (joinPromise.reject) joinPromise.reject(new Error('LoRaWAN Join Error'));
          }
        }
        
        if (fullResponse.startsWith('+RECV:')) {
          try {
            const parts = fullResponse.split(',');
            if (parts.length >= 3) {
              const hexData = parts[2].trim();
              onDataReceived(JSON.parse(hexToString(hexData)));
            }
          } catch (e) { console.error('受信データのパースに失敗:', e); }
        }

        if (!isInitializing && fullResponse.includes('Dragino OTA bootloader')) {
          console.warn('[LoRa] デバイスがリブートしました。');
          _isNetworkJoined = false;
          if (onDisconnected) onDisconnected();
        }
      }
    }
  } catch (error) {
    if (error.name !== 'AbortError') console.error('読み取りループでエラー:', error);
  }
  console.log('[LoRa] 読み取りループが停止しました。');
}

export async function connect(onData, onDisconnectCb) {
  if (_isPortConnected) return true;
  if (!navigator.serial) {
    alert('Web Serial API非対応ブラウザです。');
    return false;
  }

  isInitializing = true;

  try {
    port = await navigator.serial.requestPort();
    await port.open({ baudRate: 9600 });

    onDataReceived = onData;
    onDisconnected = onDisconnectCb;

    writer = port.writable.getWriter();
    
    const textDecoder = new TextDecoderStream();
    readableStreamClosed = port.readable.pipeTo(textDecoder.writable);
    reader = textDecoder.readable.getReader();
    
    _isPortConnected = true;
    _isNetworkJoined = false;
    
    readLoop();

    console.log('シリアルポートに接続しました。');
    return true;
  } catch (error) {
    console.error('シリアルポート接続失敗:', error);
    isInitializing = false;
    return false;
  }
}

export async function disconnect() {
  if (reader) {
    try {
      await reader.cancel();
      if (readableStreamClosed) await readableStreamClosed.catch(() => {});
    } catch(e) { /* ignore errors */ }
    reader = null;
  }
  
  if (writer) {
    try {
      writer.releaseLock();
    } catch(e) { /* ignore errors */ }
    writer = null;
  }

  if (port) {
    try {
      await port.close();
    } catch (e) { /* ignore errors */ }
    port = null;
  }

  _isPortConnected = false;
  _isNetworkJoined = false;
  isInitializing = false;
  console.log('シリアルポートを切断しました。');
}

export function join() {
  if (!_isPortConnected || !writer) return Promise.reject(new Error('ポート未接続'));
  if (isJoinCommandActive) return Promise.reject(new Error('Join処理実行中'));

  return new Promise((resolve, reject) => {
    isJoinCommandActive = true;
    joinPromise = { resolve, reject };
    const encoder = new TextEncoder();

    const writeCmd = async (cmd) => {
      console.log(`コマンド送信: ${cmd}`);
      await writer.write(encoder.encode(cmd + '\r\n'));
      await new Promise(r => setTimeout(r, 500));
    };

    const startJoinSequence = async () => {
      try {
        console.log('ネットワーク参加状態を確認します... (AT+NJS=?)');
        
        const njsPromise = new Promise((res, rej) => {
            
            // ★★★ ここから修正 ★★★
            // イベントハンドラを `checkNJSHandler` という名前に変更
            const checkNJSHandler = (event) => {
                // event.detail に受信文字列が直接入っている
                const line = event.detail; 
                
                // lineが文字列でない場合は処理を中断（安全対策）
                if (typeof line !== 'string') return;

                const trimmedLine = line.trim();
                
                if (trimmedLine === '1') {
                    document.removeEventListener('lora-line-received', checkNJSHandler);
                    res(true);
                } else if (trimmedLine === '0') {
                    document.removeEventListener('lora-line-received', checkNJSHandler);
                    res(false);
                }
            };
            
            // 作成したハンドラをイベントリスナーに登録
            document.addEventListener('lora-line-received', checkNJSHandler);
            // ★★★ ここまで修正 ★★★

            setTimeout(() => {
              // タイムアウト時には同じハンドラを削除する
              document.removeEventListener('lora-line-received', checkNJSHandler);
              rej(new Error('AT+NJS=? response timeout'));
            }, 5000);
        });

        await writeCmd('AT+NJS=?');
        const isJoined = await njsPromise;
        
        if (isJoined) {
          console.log('既にネットワークに参加済みです。Join処理をスキップします。');
          _isNetworkJoined = true;
          isJoinCommandActive = false;
          resolve(true);
          return;
        }

        console.log('ネットワークに未参加です。設定とJoinを開始します。');
        await writeCmd('AT+MODE=LWOTAA');
        await writeCmd('AT+DEVEUI=A8404168E189621F');
        await writeCmd('AT+APPEUI=A840410000000101');
        await writeCmd('AT+APPKEY=138F1A42A61329A3918FC834BCAD0071');
        await writeCmd('AT+JOIN');
        
      } catch (e) {
        isJoinCommandActive = false;
        reject(e);
      }
    };

    startJoinSequence();

    const timeoutId = setTimeout(() => {
      if (isJoinCommandActive) {
        isJoinCommandActive = false;
        reject(new Error('Join command timed out'));
      }
    }, 30000);

    joinPromise.resolve = (val) => { clearTimeout(timeoutId); resolve(val); };
    joinPromise.reject = (err) => { clearTimeout(timeoutId); reject(err); };

  }).finally(() => {
    isInitializing = false;
  });
}

export function getIsJoined() {
  return _isPortConnected && _isNetworkJoined; // 接続状態も加味
}

export async function send(data) {
  if (!writer || !_isNetworkJoined) {
    console.warn('LoRa未接続のため送信をスキップしました。');
    return;
  }
  
  const encoder = new TextEncoder();

  // 元データのバイト配列を生成
  const dataBytes = encoder.encode(data);
  // バイト配列から16進数文字列を生成
  const hexData = Array.from(dataBytes)
      .map(b => b.toString(16).padStart(2, '0')).join('');
  
  // 元データのバイト長を取得
  const dataLen = dataBytes.length;

  // AT+SENDB=<confirm_status>,<port>,<data_len>,<hexdata> の形式を厳密に適用
  const confirmStatus = 0; // 0 = Unconfirmed, 1 = Confirmed
  const fport = 2;
  const commandString = `AT+SENDB=${confirmStatus},${fport},${dataLen},${hexData}\r\n`;
  const commandBytes = encoder.encode(commandString);

  await writer.write(commandBytes);
  
  console.log(`データ送信: ${JSON.stringify(commandString)}`);
}

function hexToString(hex) {
  let str = '';
  for (let i = 0; i < hex.length; i += 2) {
    str += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
  }
  return str;
}