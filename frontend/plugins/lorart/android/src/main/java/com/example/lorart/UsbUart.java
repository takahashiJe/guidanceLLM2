package com.example.lorart;

import android.hardware.usb.*;
import android.content.Context;
import java.nio.ByteBuffer;
import java.util.HashMap;

public class UsbUart {
    private final UsbManager manager;
    private UsbDevice device;
    private UsbDeviceConnection conn;
    private UsbInterface intf;
    private UsbEndpoint epIn;
    private UsbEndpoint epOut;

    public UsbUart(Context ctx) {
        this.manager = (UsbManager) ctx.getSystemService(Context.USB_SERVICE);
    }

    public boolean open(Integer wantVid, Integer wantPid) {
        close();

        HashMap<String, UsbDevice> list = manager.getDeviceList();
        for (UsbDevice d : list.values()) {
            if (wantVid != null && wantPid != null) {
                if (d.getVendorId() != wantVid || d.getProductId() != wantPid) continue;
            }
            // 最初の CDC/通信用インタフェースを拾う（実機に合わせて調整）
            UsbInterface best = null;
            for (int i = 0; i < d.getInterfaceCount(); i++) {
                UsbInterface it = d.getInterface(i);
                // ACM: CLASS_COMM(2) + SUBCLASS_ACM(2) などをざっくり許容
                if (it.getInterfaceClass() == UsbConstants.USB_CLASS_COMM || it.getInterfaceClass() == UsbConstants.USB_CLASS_CDC_DATA) {
                    best = it;
                    break;
                }
            }
            if (best == null) continue;

            if (!manager.hasPermission(d)) {
                // 呼び出し側で requestPermission してもらう
                this.device = d; // 記録だけ
                return false;
            }

            UsbDeviceConnection c = manager.openDevice(d);
            if (c == null) continue;
            if (!c.claimInterface(best, true)) { c.close(); continue; }

            UsbEndpoint in = null, out = null;
            for (int e = 0; e < best.getEndpointCount(); e++) {
                UsbEndpoint ep = best.getEndpoint(e);
                if (ep.getType() == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                    if (ep.getDirection() == UsbConstants.USB_DIR_IN) in = ep;
                    else out = ep;
                }
            }
            if (in == null || out == null) { c.releaseInterface(best); c.close(); continue; }

            // 成功
            this.device = d;
            this.conn = c;
            this.intf = best;
            this.epIn = in;
            this.epOut = out;
            return true;
        }
        return false;
    }

    public boolean hasDeviceNoPermission() {
        return this.device != null && !manager.hasPermission(this.device);
    }

    public void close() {
        if (conn != null && intf != null) {
            try { conn.releaseInterface(intf); } catch (Exception ignore) {}
        }
        if (conn != null) {
            try { conn.close(); } catch (Exception ignore) {}
        }
        device = null; conn = null; intf = null; epIn = null; epOut = null;
    }

    public boolean writeLine(String line, int timeoutMs) {
        if (conn == null || epOut == null) return false;
        byte[] bytes = (line + "\r\n").getBytes();
        int wrote = conn.bulkTransfer(epOut, bytes, bytes.length, timeoutMs);
        return wrote == bytes.length;
    }

    public String readLine(int timeoutMs) {
        if (conn == null || epIn == null) return null;
        byte[] buf = new byte[256];
        StringBuilder sb = new StringBuilder();
        long until = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < until) {
            int n = conn.bulkTransfer(epIn, buf, buf.length, 250);
            if (n > 0) {
                for (int i = 0; i < n; i++) {
                    byte b = buf[i];
                    if (b == '\n') {
                        return sb.toString().trim();
                    } else if (b != '\r') {
                        sb.append((char) b);
                    }
                }
            }
        }
        return sb.length() > 0 ? sb.toString().trim() : null;
    }
}
