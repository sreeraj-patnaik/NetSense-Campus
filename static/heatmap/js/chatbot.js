(() => {
    const fab = document.getElementById("chatbotFab");
    const panel = document.getElementById("chatbotPanel");
    const closeBtn = document.getElementById("chatbotClose");
    const form = document.getElementById("chatbotForm");
    const input = document.getElementById("chatbotInput");
    const messages = document.getElementById("chatbotMessages");
    const status = document.getElementById("chatbotStatus");

    if (!fab || !panel || !closeBtn || !form || !input || !messages) {
        return;
    }

    const history = [];

    function setOpen(isOpen) {
        panel.classList.toggle("is-open", isOpen);
        panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
        if (isOpen) {
            input.focus();
        }
    }

    function appendMessage(role, text) {
        const bubble = document.createElement("div");
        bubble.className = `chatbot-message ${role}`;
        bubble.textContent = text;
        messages.appendChild(bubble);
        messages.scrollTop = messages.scrollHeight;
    }

    function setStatus(text) {
        if (!status) return;
        status.textContent = text;
    }

    function setLoading(isLoading) {
        if (!form || !input) return;
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = isLoading;
        }
        input.disabled = isLoading;
        setStatus(isLoading ? "Thinking..." : "");
    }

    function getCsrfToken() {
        const name = "csrftoken=";
        const cookies = document.cookie.split(";").map((c) => c.trim());
        for (const cookie of cookies) {
            if (cookie.startsWith(name)) {
                return cookie.substring(name.length);
            }
        }
        return "";
    }

    fab.addEventListener("click", () => setOpen(true));
    closeBtn.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            setOpen(false);
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text) return;

        appendMessage("user", text);
        history.push({ role: "user", text });
        input.value = "";
        setLoading(true);

        try {
            const blockSelect = document.getElementById("blockSelect");
            const floorSelect = document.getElementById("floorSelect");
            const modeSelect = document.getElementById("modeSelect");
            const providerSelect = document.getElementById("providerSelect");
            const heatmap = blockSelect && floorSelect
                ? {
                    block: blockSelect.value,
                    floor: floorSelect.value,
                    mode: modeSelect ? modeSelect.value : "wifi",
                    service_provider: providerSelect ? providerSelect.value : "all",
                }
                : null;

            const response = await fetch("/api/chatbot/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({
                    message: text,
                    history: history.slice(-6),
                    heatmap,
                }),
            });

            let data = null;
            try {
                data = await response.json();
            } catch (parseError) {
                data = null;
            }
            const answer = data?.answer || data?.error || (response.ok ? "I couldn't find that here yet." : "Assistant unavailable.");
            appendMessage("assistant", answer);
            history.push({ role: "assistant", text: answer });
        } catch (error) {
            appendMessage("assistant", "Unable to reach the assistant right now.");
            setStatus("Connection error.");
        } finally {
            setLoading(false);
            input.focus();
        }
    });
})();
