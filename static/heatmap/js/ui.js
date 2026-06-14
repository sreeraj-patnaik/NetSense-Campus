(function () {
    const header = document.querySelector(".site-header");
    const navToggle = document.querySelector(".nav-toggle");
    const navLinks = document.querySelector("[data-nav]");
    const revealTargets = document.querySelectorAll(".reveal");

    function setHeaderState() {
        if (!header) return;
        header.classList.toggle("is-scrolled", window.scrollY > 8);
    }

    function closeNavigation() {
        if (!header || !navToggle) return;
        header.classList.remove("nav-open");
        navToggle.setAttribute("aria-expanded", "false");
    }

    if (header && navToggle) {
        navToggle.addEventListener("click", () => {
            const isOpen = header.classList.toggle("nav-open");
            navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", (event) => {
            if (!header.classList.contains("nav-open")) return;
            if (header.contains(event.target)) return;
            closeNavigation();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeNavigation();
            }
        });
    }

    if (navLinks) {
        const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
        navLinks.querySelectorAll("a").forEach((link) => {
            const href = new URL(link.href, window.location.origin).pathname.replace(/\/+$/, "") || "/";
            if (href === currentPath) {
                link.setAttribute("aria-current", "page");
            }
        });
    }

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

    setHeaderState();
    window.addEventListener("scroll", setHeaderState, { passive: true });
    window.addEventListener("resize", () => {
        if (window.innerWidth > 760) {
            closeNavigation();
        }
    });
})();
