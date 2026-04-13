package com.netsense.campus;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.os.Bundle;
import android.os.Build;
import android.telephony.SubscriptionManager;
import android.telephony.TelephonyManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.core.app.ActivityCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;
import androidx.appcompat.app.AppCompatActivity;

import android.telephony.CellInfo;
import android.telephony.CellSignalStrength;
import java.util.List;

public class MainActivity extends AppCompatActivity {
    private static final String START_URL = "https://netsense-campus.onrender.com/";
    private static final int PERMISSION_REQUEST_CODE = 1001;
    private static final String NOTIFICATION_CHANNEL_ID = "netsense_alerts";
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        createNotificationChannel();
        requestRuntimePermissions();

        webView = findViewById(R.id.webview);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);

        webView.addJavascriptInterface(new NetSenseBridge(this), "NetSenseBridge");
        webView.setWebViewClient(new WebViewClient());
        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(START_URL);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (webView != null) {
            webView.saveState(outState);
        }
    }

    private void requestRuntimePermissions() {
        String[] permissions;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions = new String[] {
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
                Manifest.permission.NEARBY_WIFI_DEVICES,
                Manifest.permission.READ_PHONE_STATE,
                Manifest.permission.POST_NOTIFICATIONS
            };
        } else {
            permissions = new String[] {
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
                Manifest.permission.READ_PHONE_STATE
            };
        }
        boolean needsRequest = false;
        for (String permission : permissions) {
            if (ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED) {
                needsRequest = true;
                break;
            }
        }
        if (needsRequest) {
            ActivityCompat.requestPermissions(this, permissions, PERMISSION_REQUEST_CODE);
        }
    }

    public static class NetSenseBridge {
        private final Context context;
        private int localNotificationId = 2000;

        NetSenseBridge(Context context) {
            this.context = context.getApplicationContext();
        }

        @JavascriptInterface
        public String getNetworkInfo() {
            String mode = "unknown";
            String provider = "";
            String wifiSsid = "";
            String dbm = "";

            boolean hasLocation =
                ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION)
                    == PackageManager.PERMISSION_GRANTED;
            boolean hasCoarse =
                ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION)
                    == PackageManager.PERMISSION_GRANTED;
            boolean hasPhone =
                ContextCompat.checkSelfPermission(context, Manifest.permission.READ_PHONE_STATE)
                    == PackageManager.PERMISSION_GRANTED;
            boolean hasNearbyWifi = true;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                hasNearbyWifi =
                    ContextCompat.checkSelfPermission(context, Manifest.permission.NEARBY_WIFI_DEVICES)
                        == PackageManager.PERMISSION_GRANTED;
            }

            ConnectivityManager cm =
                (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm != null) {
                NetworkCapabilities caps = cm.getNetworkCapabilities(cm.getActiveNetwork());
                if (caps != null) {
                    if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                        mode = "wifi";
                    } else if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
                        mode = "mobile";
                    }
                }
            }

            if ("mobile".equals(mode)) {
                TelephonyManager tm =
                    (TelephonyManager) context.getSystemService(Context.TELEPHONY_SERVICE);
                if (tm != null) {
                    TelephonyManager activeTm = tm;
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && hasPhone) {
                        SubscriptionManager sm =
                            (SubscriptionManager) context.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE);
                        if (sm != null) {
                            int subId = SubscriptionManager.getDefaultDataSubscriptionId();
                            if (subId != SubscriptionManager.INVALID_SUBSCRIPTION_ID) {
                                activeTm = tm.createForSubscriptionId(subId);
                            }
                        }
                    }

                    String name = activeTm.getNetworkOperatorName();
                    if (name != null) {
                        provider = name.trim();
                    }
                    int best = Integer.MIN_VALUE;
                    if (hasPhone) {
                        try {
                            Object signal = activeTm.getSignalStrength();
                            if (signal != null) {
                                try {
                                    java.lang.reflect.Method method = signal.getClass().getMethod("getDbm");
                                    Object result = method.invoke(signal);
                                    if (result instanceof Integer) {
                                        int value = (Integer) result;
                                        if (value != Integer.MAX_VALUE && value != Integer.MIN_VALUE) {
                                            best = value;
                                        }
                                    }
                                } catch (Exception ignored) {
                                }
                            }
                        } catch (SecurityException ignored) {
                        }
                    }
                    if (best == Integer.MIN_VALUE && hasLocation) {
                        try {
                            List<CellInfo> cellInfos = activeTm.getAllCellInfo();
                            if (cellInfos != null) {
                                for (CellInfo info : cellInfos) {
                                    if (info == null || !info.isRegistered()) {
                                        continue;
                                    }
                                    CellSignalStrength strength = info.getCellSignalStrength();
                                    if (strength == null) {
                                        continue;
                                    }
                                    int value = strength.getDbm();
                                    if (value != Integer.MAX_VALUE && value != Integer.MIN_VALUE) {
                                        if (value > best) {
                                            best = value;
                                        }
                                    }
                                }
                            }
                        } catch (SecurityException ignored) {
                        }
                    }
                    if (best != Integer.MIN_VALUE) {
                        dbm = String.valueOf(best);
                    } else if (!hasLocation && !hasPhone) {
                        return "{\"error\":\"permission\",\"message\":\"Phone + Location permissions required for mobile dBm.\"}";
                    }
                }
            } else if ("wifi".equals(mode)) {
                if (!(hasLocation || hasCoarse) || !hasNearbyWifi) {
                    return "{\"error\":\"permission\",\"message\":\"Location/Nearby Devices permission required for Wi-Fi dBm/SSID.\"}";
                }
                WifiManager wm =
                    (WifiManager) context.getSystemService(Context.WIFI_SERVICE);
                if (wm != null) {
                    WifiInfo info = wm.getConnectionInfo();
                    if (info != null) {
                        String ssid = info.getSSID();
                        if (ssid != null) {
                            ssid = ssid.replace("\"", "").trim();
                            if (!ssid.isEmpty() && !ssid.toLowerCase().contains("unknown")) {
                                wifiSsid = ssid;
                                provider = ssid;
                            }
                        }
                        int rssi = info.getRssi();
                        if (rssi != Integer.MAX_VALUE && rssi != Integer.MIN_VALUE) {
                            dbm = String.valueOf(rssi);
                        }
                    }
                }
            }

            return "{\"mode\":\"" + mode + "\",\"provider\":\"" + provider + "\",\"ssid\":\"" + wifiSsid + "\",\"dbm\":\"" + dbm + "\"}";
        }

        @JavascriptInterface
        public void showNotification(String title, String body) {
            Intent intent = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
            PendingIntent pendingIntent = null;
            if (intent != null) {
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                pendingIntent = PendingIntent.getActivity(
                    context,
                    0,
                    intent,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
                );
            }

            NotificationCompat.Builder builder = new NotificationCompat.Builder(context, MainActivity.NOTIFICATION_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle(title != null && !title.isEmpty() ? title : "NetSense Update")
                .setContentText(body != null ? body : "New coverage update available.")
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .setAutoCancel(true);

            if (pendingIntent != null) {
                builder.setContentIntent(pendingIntent);
            }

            NotificationManagerCompat manager = NotificationManagerCompat.from(context);
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || ActivityCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
                    == PackageManager.PERMISSION_GRANTED) {
                manager.notify(localNotificationId++, builder.build());
            }
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            CharSequence name = "NetSense Alerts";
            String description = "Weak zone and scan notifications";
            int importance = NotificationManager.IMPORTANCE_DEFAULT;
            NotificationChannel channel = new NotificationChannel(NOTIFICATION_CHANNEL_ID, name, importance);
            channel.setDescription(description);
            NotificationManager notificationManager = getSystemService(NotificationManager.class);
            if (notificationManager != null) {
                notificationManager.createNotificationChannel(channel);
            }
        }
    }
}
