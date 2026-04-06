# NetSense Campus Android App (WebView)

This is a lightweight Android wrapper that loads the live site at:
`https://netsense-campus.onrender.com/`

## Build (Android Studio)
1. Open Android Studio.
2. Choose **Open** and select the `android/` folder.
3. Let Gradle sync.
4. **Run** to install on a device, or **Build > Build APK(s)** to export an APK.

### If Gradle sync/build fails
If your network blocks Gradle downloads, use the **embedded Gradle** that ships with Android Studio:

1. **File → Settings → Build, Execution, Deployment → Gradle**
2. Set **Use Gradle from:** `Embedded Gradle` (or `Local Gradle distribution`)
3. Sync and build again.

## Update the App
1. Increment `versionCode` and `versionName` in:
`android/app/build.gradle`
2. Rebuild the APK.
3. Reinstall on devices (or publish to Play Store for auto-updates).

## Change the URL
Edit:
`android/app/src/main/java/com/netsense/campus/MainActivity.java`
and update `START_URL`.
