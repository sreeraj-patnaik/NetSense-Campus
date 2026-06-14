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
