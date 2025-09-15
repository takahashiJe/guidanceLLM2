package com.example.lorart;

import android.app.PendingIntent;
import android.content.*;
import android.hardware.usb.*;
import com.getcapacitor.*;

import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.concurrent.*;

@CapacitorPlugin(name = "LoRaRT")
public class LoRaRTPlugin extends Plugin {
    private static final String ACTION_USB_PERMISSION = "com.example.lorart.USB_PERMISSION";
    private UsbUart uart;
    private final ExecutorService exec = Executors.newSingleThreadExecutor();

    private final BroadcastReceiver usbPermReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context ctx, Intent intent) {
            if (ACTION_USB_PERMISSION.equals(intent.getAction())) {
                // 端末の許可ダイアログの結果。ここでは何もしない（再度 join を呼んでもらう運用）
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
    }

    @Override
    protected void handleOnDestroy() {
        super.handleOnDestroy();
        try { getContext().unregisterReceiver(usbPermReceiver); } catch (Exception ignore) {}
        if (uart != null) uart.close();
        exec.shutdownNow();
    }

    private void requestUsbPermission(UsbDevice d) {
        UsbManager mgr = (UsbManager) getContext().getSystemService(Context.USB_SERVICE);
        PendingIntent pi = PendingIntent.getBroadcast(
                getContext(), 0,
                new Intent(ACTION_USB_PERMISSION),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        mgr.requestPermission(d, pi);
    }

    @PluginMethod
    public void join(PluginCall call) {
        Integer vid = null, pid = null;
        if (call.getData().has("vid")) vid = call.getInt("vid");
        if (call.getData().has("pid")) pid = call.getInt("pid");

        PluginCall saved = call;
        exec.submit(() -> {
            JSObject ret = new JSObject();
            try {
                boolean ok = uart.open(vid, pid);
                if (!ok) {
                    if (uart.hasDeviceNoPermission()) {
                        // 権限がない → リクエストして false を返す
                        UsbManager mgr = (UsbManager) getContext().getSystemService(Context.USB_SERVICE);
                        for (UsbDevice d : mgr.getDeviceList().values()) {
                            if ((vid == null || d.getVendorId() == vid) && (pid == null || d.getProductId() == pid)) {
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

                // ここから AT コマンド（例: エコーOFF→JOIN）
                uart.writeLine("AT", 500);
                uart.readLine(500);
                uart.writeLine("ATE0", 1000);
                uart.readLine(1000);

                uart.writeLine("AT+JOIN", 1000);
                // 成否待ち（最大 ~15秒）
                boolean joined = false;
                for (int i = 0; i < 30; i++) {
                    String ln = uart.readLine(500);
                    if (ln == null) continue;
                    String s = ln.toUpperCase();
                    if (s.contains("JOINED") || s.equals("OK")) { joined = true; break; }
                    if (s.contains("ERROR")) { break; }
                }

                ret.put("value", joined);
                saved.resolve(ret);
            } catch (Exception e) {
                ret.put("value", false);
                ret.put("error", e.toString());
                saved.resolve(ret);
            }
        });
    }

    @PluginMethod
    public void fetch(PluginCall call) {
        Integer code = call.getInt("code");
        Integer etag = call.getInt("etag");

        if (code == null) { call.resolve(); return; }

        PluginCall saved = call;
        exec.submit(() -> {
            try {
                // ポート未オープンなら試行（権限無ければJSにnull返す→再join運用でOK）
                if (uart == null || !uart.open(null, null)) {
                    saved.resolve(); // null相当
                    return;
                }

                // uplink（例: 01 <code> <etag>）→ 実機ATに合わせて調整
                String hex = String.format("01%02X%02X", code & 0xFF, (etag != null ? (etag & 0xFF) : 0));
                uart.writeLine("AT+SENDB=" + hex, 2000);

                // downlink待ち（最大 ~8秒）
                byte[] dl = null;
                long until = System.currentTimeMillis() + 8000;
                while (System.currentTimeMillis() < until) {
                    String ln = uart.readLine(1000);
                    if (ln == null) continue;
                    String u = ln.toUpperCase();
                    // 例: "+RECVB=xxxx" の16進を拾う（実機のURC仕様に合わせて正規化してください）
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
                    saved.resolve(); // downlinkなし → null
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
                saved.resolve(); // 例外時も null 返し（アプリ側はHTTPにフォールバック）
            }
        });
    }
}
