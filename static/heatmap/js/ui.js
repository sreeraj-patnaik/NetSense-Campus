(function () {
    const rail = document.getElementById("siteRail");
    const railToggle = document.querySelector(".rail-toggle");
    const revealTargets = document.querySelectorAll(".reveal");

    function closeRail() {
        if (!rail || !railToggle) return;
        rail.classList.remove("is-open");
        railToggle.setAttribute("aria-expanded", "false");
    }

    if (rail && railToggle) {
        railToggle.addEventListener("click", () => {
            const isOpen = rail.classList.toggle("is-open");
            railToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", (event) => {
            if (!rail.classList.contains("is-open")) return;
            if (rail.contains(event.target) || railToggle.contains(event.target)) return;
            closeRail();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeRail();
        });
    }

    const navToggles = document.querySelectorAll(".nav-toggle");

    function closeNavMenus() {
        navToggles.forEach((button) => {
            const targetId = button.getAttribute("aria-controls");
            const menu = targetId ? document.getElementById(targetId) : null;
            if (!menu) return;
            menu.classList.remove("is-open");
            button.setAttribute("aria-expanded", "false");
        });
    }

    navToggles.forEach((button) => {
        const targetId = button.getAttribute("aria-controls");
        const menu = targetId ? document.getElementById(targetId) : null;
        if (!menu) return;

        button.addEventListener("click", (event) => {
            event.stopPropagation();
            const isOpen = menu.classList.toggle("is-open");
            button.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });
    });

    document.addEventListener("click", (event) => {
        if (Array.from(navToggles).some((button) => {
            const targetId = button.getAttribute("aria-controls");
            const menu = targetId ? document.getElementById(targetId) : null;
            return menu && menu.classList.contains("is-open") && (menu.contains(event.target) || button.contains(event.target));
        })) {
            return;
        }

        closeNavMenus();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeNavMenus();
    });

    if (revealTargets.length) {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.14, rootMargin: "0px 0px -20px 0px" }
        );

        revealTargets.forEach((target) => observer.observe(target));
    }
})();
