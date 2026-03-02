(function () {
    const cfg = window.NETSENSE_CONFIG;
    const blockSelect = document.getElementById("blockSelect");
    const floorSelect = document.getElementById("floorSelect");
    const modeSelect = document.getElementById("modeSelect");
    const reloadBtn = document.getElementById("reloadBtn");
    const mapWrap = document.getElementById("mapWrap");
    const floorMap = document.getElementById("floorMap");
    const gridLayer = document.getElementById("gridLayer");
    const heatmapLayer = document.getElementById("heatmapLayer");

    function cellColor(signal) {
        if (signal >= -65) return "var(--strong)";
        if (signal >= -80) return "var(--medium)";
        return "var(--weak)";
    }

    function drawGrid() {
        const colStep = 100 / cfg.cols;
        const rowStep = 100 / cfg.rows;
        gridLayer.style.backgroundImage = [
            `repeating-linear-gradient(to right, rgba(16,32,64,0.22), rgba(16,32,64,0.22) 1px, transparent 1px, transparent ${colStep}%)`,
            `repeating-linear-gradient(to bottom, rgba(16,32,64,0.22), rgba(16,32,64,0.22) 1px, transparent 1px, transparent ${rowStep}%)`,
        ].join(",");
    }

    function setMapImage() {
        floorMap.src = cfg.floorImageTemplate;
    }

    async function loadHeatmap() {
        const params = new URLSearchParams({
            block: blockSelect.value,
            floor: floorSelect.value,
            mode: modeSelect.value,
        });
        const url = `${cfg.heatmapApiUrl}?${params.toString()}`;

        heatmapLayer.innerHTML = "";
        const response = await fetch(url);
        const points = await response.json();
        if (!Array.isArray(points)) return;

        const mapRect = mapWrap.getBoundingClientRect();
        const cellWidth = mapRect.width / cfg.cols;
        const cellHeight = mapRect.height / cfg.rows;

        points.forEach((point) => {
            const node = document.createElement("div");
            node.style.position = "absolute";
            node.style.left = `${point.cell_x * cellWidth}px`;
            node.style.top = `${point.cell_y * cellHeight}px`;
            node.style.width = `${cellWidth}px`;
            node.style.height = `${cellHeight}px`;
            node.style.background = cellColor(point.signal);
            node.title = `Signal: ${point.signal} dBm (${point.count} scans)`;
            heatmapLayer.appendChild(node);
        });
    }

    async function refresh() {
        setMapImage();
        drawGrid();
        await loadHeatmap();
    }

    reloadBtn.addEventListener("click", refresh);
    blockSelect.addEventListener("change", refresh);
    floorSelect.addEventListener("change", refresh);
    modeSelect.addEventListener("change", refresh);
    window.addEventListener("resize", loadHeatmap);

    refresh();
})();
