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
        navigator.serviceWorker.register("/sw.js").catch((error) => {
            console.warn("Service worker registration failed:", error);
        });
    });

    window.addEventListener("beforeinstallprompt", (event) => {
        event.preventDefault();
        deferredPrompt = event;
        if (installBtn) installBtn.hidden = false;
        setStatus("");
    });

    if (installBtn) {
        installBtn.addEventListener("click", async () => {
            if (isIos()) {
                setStatus("On iPhone or iPad, use Share then Add to Home Screen.");
                return;
            }
            if (!deferredPrompt) {
                setStatus("Install is not ready yet. Use the browser menu to install the app.");
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
        setStatus("On iPhone or iPad, use Share then Add to Home Screen.");
    }

    if (installBtn && !isIos()) {
        installBtn.hidden = false;
        setStatus("If no prompt appears, use the browser menu to install the app.");
    }
})();
