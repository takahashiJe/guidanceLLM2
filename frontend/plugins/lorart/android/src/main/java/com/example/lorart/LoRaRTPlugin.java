package com.example.lorart;

import android.app.PendingIntent;
import android.content.*;
import android.hardware.usb.*;
import android.util.Log;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@CapacitorPlugin(name = "LoRaRT")
public class LoRaRTPlugin extends Plugin {
    private static final String TAG = "LoRaRT";
    private static final String ACTION_USB_PERMISSION = "com.example.lorart.USB_PERMISSION";

    private UsbUart uart;
    private final ExecutorService exec = Executors.newSingleThreadExecutor();

    private final BroadcastReceiver usbPermReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context ctx, Intent intent) {
            if (ACTION_USB_PERMISSION.equals(intent.getAction())) {
                // ここでは特に何もしない（JS 側で join を再実行する運用）
                Log.d(TAG, "USB permission result received");
            }
        }
    };

    @Override
    public void load() {
        super.load();
        this.uart = new UsbUart(getContext());

        // USB Permission 受け取り
        IntentFilter filter = new IntentFilter(ACTION_USB_PERMISSION);
        getContext().registerReceiver(usbPermReceiver, filter);
        Log.d(TAG, "LoRaRT plugin loaded");
    }

    @Override
    protected void handleOnDestroy() {
        super.handleOnDestroy();
        try { getContext().unregisterReceiver(usbPermReceiver); } catch (Exception ignore) {}
        if (uart != null) uart.close();
        exec.shutdownNow();
        Log.d(TAG, "LoRaRT plugin destroyed");
    }

    private void requestUsbPermission(UsbDevice d) {
        UsbManager mgr = (UsbManager) getContext().getSystemService(Context.USB_SERVICE);
        PendingIntent pi = PendingIntent.getBroadcast(
                getContext(), 0,
                new Intent(ACTION_USB_PERMISSION),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        mgr.requestPermission(d, pi);
    }

    @com.getcapacitor.PluginMethod
    public void join(PluginCall call) {
        // ★ ラムダで使うために final コピーを作る
        final Integer fVid = call.getData().has("vid") ? call.getInt("vid") : null;
        final Integer fPid = call.getData().has("pid") ? call.getInt("pid") : null;

        final PluginCall saved = call;
        exec.submit(() -> {
            JSObject ret = new JSObject();
            try {
                Log.d(TAG, "join() called vid=" + fVid + " pid=" + fPid);
                boolean ok = uart.open(fVid, fPid);
                if (!ok) {
                    if (uart.hasDeviceNoPermission()) {
                        // 権限がない → リクエストして false を返す
                        UsbManager mgr = (UsbManager) getContext().getSystemService(Context.USB_SERVICE);
                        for (UsbDevice d : mgr.getDeviceList().values()) {
                            boolean vidOk = (fVid == null || d.getVendorId() == fVid);
                            boolean pidOk = (fPid == null || d.getProductId() == fPid);
                            if (vidOk && pidOk) {
                                Log.d(TAG, "requesting USB permission for device " + d);
                                requestUsbPermission(d);
                                break;
                            }
                        }
                        ret.put("value", false);
                        ret.put("reason", "no_permission");
                        saved.resolve(ret);
                        return;
                    }
                    ret.put("value", false);
                    ret.put("reason", "no_device");
                    saved.resolve(ret);
                    return;
                }

                // AT 初期化 → JOIN
                uart.writeLine("AT", 500);
                uart.readLine(500);
                uart.writeLine("ATE0", 1000);
                uart.readLine(1000);

                uart.writeLine("AT+JOIN", 1000);
                boolean joined = false;
                for (int i = 0; i < 30; i++) { // ~15秒
                    String ln = uart.readLine(500);
                    if (ln == null) continue;
                    String s = ln.trim().toUpperCase();
                    Log.d(TAG, "JOIN resp: " + s);
                    if (s.contains("JOINED") || s.equals("OK")) { joined = true; break; }
                    if (s.contains("ERROR")) { break; }
                }

                ret.put("value", joined);
                saved.resolve(ret);
            } catch (Exception e) {
                Log.e(TAG, "join() error", e);
                ret.put("value", false);
                ret.put("error", e.toString());
                saved.resolve(ret);
            }
        });
    }

    @com.getcapacitor.PluginMethod
    public void fetch(PluginCall call) {
        final Integer fCode = call.getInt("code");
        final Integer fEtag = call.getInt("etag");
        final PluginCall saved = call;

        if (fCode == null) {
            saved.resolve(); // null 相当
            return;
        }

        exec.submit(() -> {
            try {
                // ポート未オープンなら試行（権限無ければJSにnull返す→HTTPにフォールバック）
                if (uart == null || !uart.open(null, null)) {
                    Log.d(TAG, "fetch() uart not open");
                    saved.resolve();
                    return;
                }

                // uplink（例: 01 <code> <etag>）→ 実機 AT に合わせて要調整
                String hex = String.format("01%02X%02X", (fCode & 0xFF), (fEtag != null ? (fEtag & 0xFF) : 0));
                Log.d(TAG, "uplink hex=" + hex);
                uart.writeLine("AT+SENDB=" + hex, 2000);

                // downlink 待ち（~8秒）
                byte[] dl = null;
                long until = System.currentTimeMillis() + 8000;
                while (System.currentTimeMillis() < until) {
                    String ln = uart.readLine(1000);
                    if (ln == null) continue;
                    String u = ln.toUpperCase();
                    Log.d(TAG, "downlink ln=" + u);
                    int idx = u.indexOf("+RECVB=");
                    if (idx >= 0) {
                        String hexPay = ln.substring(idx + 7).trim().replaceAll("[^0-9A-Fa-f]", "");
                        if (hexPay.length() >= 2) {
                            int n = hexPay.length() / 2;
                            dl = new byte[n];
                            for (int i = 0; i < n; i++) {
                                dl[i] = (byte) Integer.parseInt(hexPay.substring(i * 2, i * 2 + 2), 16);
                            }
                            break;
                        }
                    }
                }

                if (dl == null || dl.length == 0) {
                    Log.d(TAG, "no downlink");
                    saved.resolve(); // null
                    return;
                }

                // 1〜2B をデコード（B0: w(2)<<6 | u(2)<<4 | c(3)<<1 | hasH(1), B1: h?）
                int b0 = dl[0] & 0xFF;
                int w = (b0 >> 6) & 0x03;
                int u = (b0 >> 4) & 0x03;
                int c = (b0 >> 1) & 0x07;
                boolean hasH = (b0 & 0x01) == 1;
                Integer h = null;
                if (hasH && dl.length >= 2) h = dl[1] & 0xFF;

                JSObject out = new JSObject();
                out.put("w", w);
                out.put("u", u);
                out.put("c", c);
                if (h != null) out.put("h", h);
                saved.resolve(out);
            } catch (Exception e) {
                Log.e(TAG, "fetch() error", e);
                saved.resolve(); // 例外時も null 返し（アプリ側はHTTPにフォールバック）
            }
        });
    }
}
