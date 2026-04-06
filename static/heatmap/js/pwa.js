(function () {
    const installBtn = document.getElementById("installAppBtn");
    let deferredPrompt = null;

    if (!("serviceWorker" in navigator)) return;

    window.addEventListener("load", () => {
        navigator.serviceWorker
            .register("/sw.js")
            .catch((error) => {
                console.warn("Service worker registration failed:", error);
            });
    });

    window.addEventListener("beforeinstallprompt", (event) => {
        event.preventDefault();
        deferredPrompt = event;
        if (installBtn) {
            installBtn.hidden = false;
        }
    });

    if (installBtn) {
        installBtn.addEventListener("click", async () => {
            if (!deferredPrompt) return;
            deferredPrompt.prompt();
            await deferredPrompt.userChoice;
            deferredPrompt = null;
            installBtn.hidden = true;
        });
    }
})();
