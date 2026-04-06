(function () {
    const installBtn = document.getElementById("installAppBtn");
    const installStatus = document.getElementById("installAppStatus");
    let deferredPrompt = null;

    if (!("serviceWorker" in navigator)) return;

    function setStatus(message) {
        if (!installStatus) return;
        installStatus.textContent = message;
        installStatus.hidden = !message;
    }

    function isIos() {
        return /iphone|ipad|ipod/i.test(navigator.userAgent);
    }

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
        if (installBtn) installBtn.hidden = false;
    });

    if (installBtn) {
        installBtn.addEventListener("click", async () => {
            if (isIos()) {
                setStatus("On iOS: Share -> Add to Home Screen.");
                return;
            }
            if (!deferredPrompt) {
                setStatus("Install not ready yet. Try again or use browser menu.");
                return;
            }
            deferredPrompt.prompt();
            await deferredPrompt.userChoice;
            deferredPrompt = null;
            installBtn.hidden = true;
            setStatus("");
        });
    }

    if (isIos() && installBtn) {
        installBtn.hidden = false;
        setStatus("On iOS: Share -> Add to Home Screen.");
    }
})();
