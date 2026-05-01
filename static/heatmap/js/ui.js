(function () {
    const header = document.querySelector(".site-header");
    const navToggle = document.querySelector(".nav-toggle");
    const revealTargets = document.querySelectorAll(".reveal");
    const parallaxTargets = document.querySelectorAll("[data-parallax]");

    if (header && navToggle) {
        navToggle.addEventListener("click", () => {
            const isOpen = header.classList.toggle("nav-open");
            navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", (event) => {
            if (!header.classList.contains("nav-open")) return;
            if (header.contains(event.target)) return;
            header.classList.remove("nav-open");
            navToggle.setAttribute("aria-expanded", "false");
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
            { threshold: 0.14, rootMargin: "0px 0px -30px 0px" }
        );
        revealTargets.forEach((target) => observer.observe(target));
    }

    if (parallaxTargets.length) {
        const updateParallax = () => {
            const viewportMid = window.innerHeight / 2;
            parallaxTargets.forEach((el) => {
                const speed = Number(el.dataset.parallax || 0.08);
                const rect = el.getBoundingClientRect();
                const itemMid = rect.top + rect.height / 2;
                const offset = (itemMid - viewportMid) * speed * -1;
                el.style.transform = `translate3d(0, ${offset.toFixed(2)}px, 0)`;
            });
        };
        window.addEventListener("scroll", updateParallax, { passive: true });
        window.addEventListener("resize", updateParallax);
        updateParallax();
    }
})();
