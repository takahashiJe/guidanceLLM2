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
    await port.open({ baudRate: 9600 }); // Androidで成功した9600に固定

    const textEncoder = new TextEncoderStream();
    port.writable.pipeTo(textEncoder.writable);
    writer = textEncoder.writable.getWriter();
    
    const textDecoder = new TextDecoderStream();
    port.readable.pipeTo(textDecoder.readable);
    reader = textDecoder.readable.getReader();

    console.log('シリアルポートに接続しました。');
    return true;
  } catch (error) {
    console.error('シリアルポートへの接続に失敗しました:', error);
    port = null;
    return false;
  }
}

/**
 * ★★★ 解決策：ストリームロックエラーに対応した堅牢な切断処理 ★★★
 */
export async function disconnect() {
  if (writer) {
    // writerはロックを気にせずクローズできる
    try { await writer.close(); } catch (e) {}
    writer = null;
  }
  if (reader) {
    // readerはロックされている可能性があるので、丁寧にキャンセルする
    try { await reader.cancel(); } catch (e) {}
    reader = null;
  }
  if (port) {
    // reader/writerが解放された後にポートを閉じる
    try { await port.close(); } catch (e) {}
    port = null;
  }
  console.log('シリアルポートを切断しました。');
}

/**
 * ★★★ 解決策：デバイスの挙動に合わせたJOINシーケンス ★★★
 * 設定コマンドは応答を期待せず、一方的に送信 (Fire and Forget) する。
 */
export async function join() {
    if (!writer || !reader) {
        console.error('シリアルポートが準備できていません。');
        return false;
    }

    // 応答を待たずに設定コマンドを送信
    const commands = [
      'AT+MODE=LWOTAA',
      'AT+DEVEUI=A8404168E189621F',
      'AT+APPEUI=A840410000000101',
      'AT+APPKEY=138F1A42A61329A3918FC834BCAD0071'
    ];
    for (const cmd of commands) {
      console.log(`設定コマンド送信: ${cmd}`);
      await writer.write(`${cmd}\r\n`);
      await new Promise(resolve => setTimeout(resolve, 200)); // コマンド間に短い待機
    }
    
    console.log('ネットワークに参加します... (AT+JOIN)');
    await writer.write('AT+JOIN\r\n');

    // Androidターミナルで確認できた "JOINED" という文字列を待つ
    const readTimeout = 30000; // 30秒
    try {
      let fullResponse = '';
      const startTime = Date.now();
      while(Date.now() - startTime < readTimeout) {
        const { value, done } = await reader.read();

        if (done) break;
        
        fullResponse += value;
        console.log(`JOIN応答待機中... 受信: ${value.trim()}`);
        
        // "JOINED" または "+JOIN: OK" の文字列が含まれていたら成功
        if (fullResponse.includes('JOINED') || fullResponse.includes('+JOIN: OK')) {
          console.log("LoRaWAN参加成功！");
          return true;
        }
        if (fullResponse.includes('Failed')) {
          console.error("LoRaWAN参加失敗");
          return false;
        }
      }
      // ループを抜けたらタイムアウト
      throw new Error('Timeout');

    } catch(e) {
      console.error('JOIN応答待機中にタイムアウトしました。', e);
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
    // 送信コマンドも応答を期待しない
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