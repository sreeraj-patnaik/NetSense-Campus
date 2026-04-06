(function () {
    const header = document.querySelector(".site-header");
    const navToggle = document.querySelector(".nav-toggle");
    if (header && navToggle) {
        navToggle.addEventListener("click", () => {
            const isOpen = header.classList.toggle("nav-open");
            navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });
        const navLinks = header.querySelectorAll(".nav-links a");
        navLinks.forEach((link) => {
            link.addEventListener("click", () => {
                if (!header.classList.contains("nav-open")) return;
                header.classList.remove("nav-open");
                navToggle.setAttribute("aria-expanded", "false");
            });
        });
        document.addEventListener("click", (event) => {
            if (!header.classList.contains("nav-open")) return;
            if (header.contains(event.target)) return;
            header.classList.remove("nav-open");
            navToggle.setAttribute("aria-expanded", "false");
        });
    }
    const revealTargets = document.querySelectorAll(".reveal");
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
            { threshold: 0.2 }
        );
        revealTargets.forEach((target) => observer.observe(target));
    }

    const parallaxItems = Array.from(document.querySelectorAll("[data-parallax]"));
    if (!parallaxItems.length) return;

    let ticking = false;

    function updateParallax() {
        parallaxItems.forEach((item) => {
            const speed = Number(item.dataset.parallax || 0.15);
            const rect = item.getBoundingClientRect();
            const viewportMid = window.innerHeight / 2;
            const itemMid = rect.top + rect.height / 2;
            const offset = (itemMid - viewportMid) * speed * -1;
            item.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0)`;
        });
        ticking = false;
    }

    function onScroll() {
        if (!ticking) {
            window.requestAnimationFrame(updateParallax);
            ticking = true;
        }
    }

    window.addEventListener("scroll", onScroll);
    window.addEventListener("resize", updateParallax);
    updateParallax();
})();

