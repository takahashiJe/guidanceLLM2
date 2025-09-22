let port = null;
let reader = null;
let writer = null;

// シリアルポートに接続し、読み書きの準備をする
export async function connect() {
  if (!navigator.serial) {
    alert('お使いのブラウザはWeb Serial APIをサポートしていません。');
    return false;
  }
  try {
    port = await navigator.serial.requestPort();
    await port.open({ baudRate: 9600 });

    const textEncoder = new TextEncoderStream();
    textEncoder.readable.pipeTo(port.writable);
    writer = textEncoder.writable.getWriter();
    
    const textDecoder = new TextDecoderStream();
    port.readable.pipeTo(textDecoder.writable);
    reader = textDecoder.readable.getReader();

    console.log('シリアルポートに接続しました。');
    return true;
  } catch (error) {
    console.error('シリアルポートへの接続に失敗しました:', error);
    port = null;
    return false;
  }
}

// ストリームロックエラーに対応した堅牢な切断処理
export async function disconnect() {
  if (writer) {
    try { await writer.close(); } catch (e) {}
    writer = null;
  }
  if (reader) {
    try { await reader.cancel(); } catch (e) {}
    reader = null;
  }
  if (port) {
    try { await port.close(); } catch (e) {}
    port = null;
  }
  console.log('シリアルポートを切断しました。');
}

// デバイスの挙動に合わせたJOINシーケンス
export async function join() {
    if (!writer || !reader) {
        console.error('シリアルポートが準備できていません。');
        return false;
    }

    // 応答を待たずに設定コマンドを送信
    const commands = [
      'ATZ', // ★★★ 念のためアダプターをリセットして初期状態にする
      'AT+MODE=LWOTAA',
      'AT+DEVEUI=A8404168E189621F',
      'AT+APPEUI=A840410000000101',
      'AT+APPKEY=138F1A42A61329A3918FC834BCAD0071'
    ];
    for (const cmd of commands) {
      console.log(`設定コマンド送信: ${cmd}`);
      await writer.write(`${cmd}\r\n`);
      await new Promise(resolve => setTimeout(resolve, 500)); // コマンド間に少し待機
    }
    
    console.log('ネットワークに参加します... (AT+JOIN)');
    await writer.write('AT+JOIN\r\n');

    const readTimeout = 30000;
    try {
      let fullResponse = '';
      const startTime = Date.now();
      while(Date.now() - startTime < readTimeout) {
        const { value, done } = await reader.read();
        if (done) break;
        
        fullResponse += value;
        console.log(`JOIN応答待機中... 受信: ${value.trim()}`);
        
        if (fullResponse.includes('JOINED') || fullResponse.includes('+JOIN: OK')) {
          console.log("LoRaWAN参加成功！セッション情報を保存します...");
          
          // ★★★★★★★ 解決策 ★★★★★★★
          // JOIN成功後、設定を保存するコマンドを送信する
          await writer.write('AT+SAVE\r\n');
          await new Promise(resolve => setTimeout(resolve, 1000)); // 保存処理を待つ
          console.log("保存完了。データ送信を開始できます。");
          // ★★★★★★★★★★★★★★★★★
          
          return true;
        }
        if (fullResponse.includes('Failed')) {
          console.error("LoRaWAN参加失敗");
          return false;
        }
      }
      throw new Error('Timeout');
    } catch(e) {
      console.error('JOIN応答待機中にタイムアウトまたはエラー:', e);
      return false;
    }
}

// 現在のネットワーク参加状態を確認する
export async function isJoined() {
  if (!writer || !reader) return false;

  await writer.write('AT+NJS\r\n');
  
  const readTimeout = 3000; // 3秒以内に応答があるはず
  try {
    const startTime = Date.now();
    let response = '';
    while (Date.now() - startTime < readTimeout) {
      const { value, done } = await reader.read();
      if (done) break;
      response += value;
      // "AT+NJS=1" のように応答が返ってくることを期待
      if (response.includes('AT+NJS=1') || response.trim() === '1') {
        console.log('[LoRa Status] ネットワーク参加済みです。');
        return true;
      }
      if (response.includes('AT+NJS=0') || response.trim() === '0') {
         console.log('[LoRa Status] ネットワークに未参加です。');
        return false;
      }
    }
    // タイムアウトした場合も未参加とみなす
    console.log('[LoRa Status] 状態確認がタイムアウトしました。');
    return false;
  } catch (e) {
    console.error('Join状態の確認中にエラー:', e);
    return false;
  }
}

// データを送信 (Uplink)
export async function send(data) {
    if (!writer) return;
    const hexData = Array.from(new TextEncoder().encode(data))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    
    const command = `AT+SEND=2:${hexData}`;
    console.log(`データ送信: ${command}`);
    await writer.write(`${command}\r\n`);
}

// データ受信ループを開始 (Downlink)
export async function startReceiveLoop(onData) {
    if (!reader) return;
    console.log('ダウンリンク受信ループを開始します...');
    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            const lines = value.split(/[\r\n]+/).filter(line => line.trim() !== '');
            for (const line of lines) {
              if (line.startsWith('+RECV:')) {
                  console.log(`ダウンリンク受信: ${line}`);
                  const parts = line.split(',');
                  if (parts.length >= 3) {
                      const hexData = parts[2].trim();
                      try {
                        const jsonData = hexToString(hexData);
                        onData(JSON.parse(jsonData));
                      } catch (e) {
                        console.error('受信データのパースに失敗:', e, {hexData});
                      }
                  }
              }
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
          console.log('受信ループが正常に停止しました。');
        } else {
          console.error('受信ループでエラーが発生しました:', error);
        }
    }
}

function hexToString(hex) {
    let str = '';
    for (let i = 0; i < hex.length; i += 2) {
        str += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
    }
    return str;
}