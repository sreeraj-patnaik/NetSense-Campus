(function () {
    const revealTargets = document.querySelectorAll("[data-reveal]");
    const hero = document.querySelector(".marketing-hero");
    const particleLayer = document.querySelector(".hero-particles");

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
            { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
        );

        revealTargets.forEach((target) => observer.observe(target));
    }

    if (particleLayer) {
        const particleCount = window.matchMedia("(max-width: 760px)").matches ? 10 : 18;
        for (let index = 0; index < particleCount; index += 1) {
            const particle = document.createElement("span");
            particle.className = "hero-particle";
            const left = Math.random() * 100;
            const size = 3 + Math.random() * 5;
            const duration = 12 + Math.random() * 12;
            const delay = -Math.random() * duration;
            particle.style.left = `${left}%`;
            particle.style.setProperty("--duration", `${duration}s`);
            particle.style.setProperty("--x-start", `${(Math.random() * 40) - 20}px`);
            particle.style.setProperty("--x-end", `${(Math.random() * 60) - 30}px`);
            particle.style.width = `${size}px`;
            particle.style.height = `${size}px`;
            particle.style.animationDelay = `${delay}s`;
            particleLayer.appendChild(particle);
        }
    }

    if (!hero) {
        return;
    }

    let frame = 0;
    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;

    function animate() {
        currentX += (targetX - currentX) * 0.08;
        currentY += (targetY - currentY) * 0.08;
        hero.style.setProperty("--hero-parallax-x", `${currentX}px`);
        hero.style.setProperty("--hero-parallax-y", `${currentY}px`);
        const settled = Math.abs(targetX - currentX) < 0.05 && Math.abs(targetY - currentY) < 0.05;
        if (settled) {
            frame = 0;
            return;
        }
        frame = window.requestAnimationFrame(animate);
    }

    hero.addEventListener("pointermove", (event) => {
        const rect = hero.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        targetX = ((event.clientX - centerX) / rect.width) * 18;
        targetY = ((event.clientY - centerY) / rect.height) * 18;
        if (!frame) {
            frame = window.requestAnimationFrame(animate);
        }
    });

    hero.addEventListener("pointerleave", () => {
        targetX = 0;
        targetY = 0;
        if (!frame) {
            frame = window.requestAnimationFrame(animate);
        }
    });
})();
