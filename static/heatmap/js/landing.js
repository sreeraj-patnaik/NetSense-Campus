(function () {
    const revealTargets = document.querySelectorAll(".card, .timeline-step, .flow-node, .accordion details");
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("in-view");
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.15 }
    );

    revealTargets.forEach((target) => observer.observe(target));
})();
