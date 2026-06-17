(() => {
    const cfg = window.NETSENSE_ASSISTANT_CONFIG || {};
    const fab = document.getElementById("chatbotFab");
    const panel = document.getElementById("chatbotPanel");
    const closeBtn = document.getElementById("chatbotClose");
    const form = document.getElementById("chatbotForm");
    const input = document.getElementById("chatbotInput");
    const messages = document.getElementById("chatbotMessages");
    const suggestions = document.getElementById("chatbotSuggestions");
    const status = document.getElementById("chatbotStatus");

    if (!fab || !panel || !closeBtn || !form || !input || !messages) {
        return;
    }

    const history = [];
    const defaultAuthenticatedSuggestions = [
        { label: "What is this app for?", message: "What is this app for?" },
        { label: "My institution", message: "What is my institution name?" },
        { label: "Current signal", message: "What are my current signal strengths?" },
        { label: "Best provider", message: "Which provider performs best in my institution?" },
        { label: "Weak zones", message: "Show weak signal areas." },
        { label: "Compare floors", message: "Compare floors in my institution." },
    ];
    const defaultGuestSuggestions = [
        { label: "Sign in", href: cfg.loginUrl || "/login/" },
        { label: "What is this app for?", message: "What is this app for?" },
        { label: "My institution", message: "What is my institution name?" },
        { label: "Live coverage", message: "What are my current signal strengths?" },
        { label: "Best provider", message: "Which provider performs best?" },
    ];

    function getDefaultSuggestions() {
        return cfg.isAuthenticated ? defaultAuthenticatedSuggestions : defaultGuestSuggestions;
    }

    function setOpen(isOpen) {
        panel.classList.toggle("is-open", isOpen);
        panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
        fab.setAttribute("aria-expanded", isOpen ? "true" : "false");
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

    function clearSuggestions() {
        if (!suggestions) return;
        suggestions.innerHTML = "";
    }

    function submitQuickReply(text) {
        input.value = text;
        form.requestSubmit();
    }

    function renderSuggestions(items) {
        if (!suggestions) return;
        const choices = Array.isArray(items) && items.length ? items : getDefaultSuggestions();
        suggestions.innerHTML = "";

        choices.forEach((choice) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "chatbot-chip";
            button.textContent = choice.label || choice.message || "Option";
            button.addEventListener("click", () => {
                if (choice.href) {
                    window.location.href = choice.href;
                    return;
                }
                if (choice.message) {
                    submitQuickReply(choice.message);
                }
            });
            suggestions.appendChild(button);
        });
    }

    async function sendMessage(text) {
        appendMessage("user", text);
        history.push({ role: "user", text });
        input.value = "";
        clearSuggestions();
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
                    is_authenticated: Boolean(cfg.isAuthenticated),
                    current_institution_name: cfg.currentInstitutionName || "",
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
            renderSuggestions(data?.choices || []);
        } catch (error) {
            appendMessage("assistant", "Unable to reach the assistant right now.");
            renderSuggestions(getDefaultSuggestions());
            setStatus("Connection error.");
        } finally {
            setLoading(false);
            input.focus();
        }
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
        await sendMessage(text);
    });

    renderSuggestions(getDefaultSuggestions());
})();
