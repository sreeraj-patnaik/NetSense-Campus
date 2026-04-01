(function () {
    const cfg = window.NETSENSE_CONFIG;
    const blockSelect = document.getElementById("blockSelect");
    const floorSelect = document.getElementById("floorSelect");
    const modeSelect = document.getElementById("modeSelect");
    const providerSelect = document.getElementById("providerSelect");
    const reloadBtn = document.getElementById("reloadBtn");
    const renderModeSelect = document.getElementById("renderModeSelect");
    const interpolateToggle = document.getElementById("interpolateToggle");
    const autoSmoothToggle = document.getElementById("autoSmoothToggle");
    const confidenceToggle = document.getElementById("confidenceToggle");
    const spreadRange = document.getElementById("spreadRange");
    const legendMin = document.getElementById("legendMin");
    const legendMax = document.getElementById("legendMax");
    const mapWrap = document.getElementById("mapWrap");
    const floorMap = document.getElementById("floorMap");
    const gridLayer = document.getElementById("gridLayer");
    const heatmapCanvas = document.getElementById("heatmapCanvas");
    const heatmapCtx = heatmapCanvas.getContext("2d");
    let rows = cfg.rows;
    let cols = cfg.cols;

    function selectedKey() {
        return `${blockSelect.value}:${floorSelect.value}`;
    }

    function selectedFloorConfig() {
        return cfg.floorConfigs?.[selectedKey()] || {};
    }

    function floorsForBlock(block) {
        return cfg.blockFloors?.[block] || [];
    }

    function syncFloorOptions() {
        const floors = floorsForBlock(blockSelect.value);
        const currentValue = floorSelect.value;
        floorSelect.innerHTML = "";

        floors.forEach((floor) => {
            const option = document.createElement("option");
            option.value = String(floor);
            option.textContent = String(floor);
            floorSelect.appendChild(option);
        });

        if (floors.length === 0) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No floors";
            floorSelect.appendChild(option);
            floorSelect.disabled = true;
            return;
        }

        floorSelect.disabled = false;
        floorSelect.value = floors.map(String).includes(currentValue) ? currentValue : String(floors[0]);
    }

    function lerp(a, b, t) {
        return a + (b - a) * t;
    }

    function clamp01(value) {
        return Math.max(0, Math.min(1, value));
    }

    function colorRamp(t) {
        const stops = [
            { t: 0.0, c: [209, 52, 52] },
            { t: 0.5, c: [240, 196, 33] },
            { t: 1.0, c: [34, 163, 74] },
        ];
        const clamped = clamp01(t);
        for (let i = 1; i < stops.length; i += 1) {
            const prev = stops[i - 1];
            const next = stops[i];
            if (clamped <= next.t) {
                const localT = (clamped - prev.t) / (next.t - prev.t);
                return [
                    Math.round(lerp(prev.c[0], next.c[0], localT)),
                    Math.round(lerp(prev.c[1], next.c[1], localT)),
                    Math.round(lerp(prev.c[2], next.c[2], localT)),
                ];
            }
        }
        return stops[stops.length - 1].c;
    }

    function colorRampInterpolated(t) {
        const stops = [
            { t: 0.0, c: [42, 104, 216] },
            { t: 0.5, c: [47, 194, 224] },
            { t: 1.0, c: [140, 225, 255] },
        ];
        const clamped = clamp01(t);
        for (let i = 1; i < stops.length; i += 1) {
            const prev = stops[i - 1];
            const next = stops[i];
            if (clamped <= next.t) {
                const localT = (clamped - prev.t) / (next.t - prev.t);
                return [
                    Math.round(lerp(prev.c[0], next.c[0], localT)),
                    Math.round(lerp(prev.c[1], next.c[1], localT)),
                    Math.round(lerp(prev.c[2], next.c[2], localT)),
                ];
            }
        }
        return stops[stops.length - 1].c;
    }

    function drawGrid() {
        const colStep = 100 / cols;
        const rowStep = 100 / rows;
        gridLayer.style.backgroundImage = [
            `repeating-linear-gradient(to right, rgba(16,32,64,0.22), rgba(16,32,64,0.22) 1px, transparent 1px, transparent ${colStep}%)`,
            `repeating-linear-gradient(to bottom, rgba(16,32,64,0.22), rgba(16,32,64,0.22) 1px, transparent 1px, transparent ${rowStep}%)`,
        ].join(",");
    }

    function setMapImage() {
        const floorCfg = selectedFloorConfig();
        floorMap.src = floorCfg.image_url || cfg.defaultFloorImage;
    }

    function applyFloorDimensions() {
        const floorCfg = selectedFloorConfig();
        rows = Math.max(1, Number(floorCfg.rows || cfg.rows));
        cols = Math.max(1, Number(floorCfg.cols || cfg.cols));
        mapWrap.dataset.rows = String(rows);
        mapWrap.dataset.cols = String(cols);
        drawGrid();
    }

    function waitForImageLoad() {
        return new Promise((resolve) => {
            if (floorMap.complete && floorMap.naturalWidth > 0) {
                resolve();
                return;
            }
            const onLoad = () => {
                floorMap.removeEventListener("load", onLoad);
                resolve();
            };
            floorMap.addEventListener("load", onLoad);
        });
    }

    async function loadHeatmap() {
        if (!floorSelect.value) {
            heatmapCtx.clearRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
            return;
        }

        const params = new URLSearchParams({
            block: blockSelect.value,
            floor: floorSelect.value,
            mode: modeSelect.value,
        });
        params.set("interpolate", interpolateToggle.checked ? "1" : "0");
        if (providerSelect.value) {
            params.set("service_provider", providerSelect.value);
        }
        const url = `${cfg.heatmapApiUrl}?${params.toString()}`;

        const response = await fetch(url);
        const points = await response.json();
        if (!Array.isArray(points)) return;

        const mapRect = mapWrap.getBoundingClientRect();
        if (!mapRect.width || !mapRect.height) {
            requestAnimationFrame(loadHeatmap);
            return;
        }
        const cellWidth = mapRect.width / cols;
        const cellHeight = mapRect.height / rows;
        const canvasWidth = Math.max(1, Math.floor(mapRect.width));
        const canvasHeight = Math.max(1, Math.floor(mapRect.height));
        heatmapCanvas.width = canvasWidth;
        heatmapCanvas.height = canvasHeight;
        heatmapCtx.clearRect(0, 0, canvasWidth, canvasHeight);

        const realPoints = points.filter((point) => !point.interpolated);
        const scalePoints = realPoints.length ? realPoints : points;
        const signals = scalePoints.map((point) => point.signal);
        const minSignal = Math.min(...signals);
        const maxSignal = Math.max(...signals);
        const range = Math.max(1, maxSignal - minSignal);
        legendMin.textContent = `${minSignal.toFixed(1)} dBm`;
        legendMax.textContent = `${maxSignal.toFixed(1)} dBm`;

        const renderMode = renderModeSelect.value;
        const renderPoints = interpolateToggle.checked ? points : points.filter((point) => !point.interpolated);
        const density = realPoints.length / Math.max(1, rows * cols);
        const autoSpread = 2.2 - Math.min(1, density * 2.2) * 1.1;
        const manualSpread = Math.max(0.6, Number(spreadRange.value || 1.6));
        const spreadMultiplier = autoSmoothToggle?.checked ? autoSpread : manualSpread;
        if (autoSmoothToggle?.checked) {
            spreadRange.value = spreadMultiplier.toFixed(1);
        }
        spreadRange.disabled = autoSmoothToggle?.checked;

        renderPoints.forEach((point) => {
            const normalized = clamp01((point.signal - minSignal) / range);
            const banded = renderMode === "contour" ? Math.round(normalized * 6) / 6 : normalized;
            const [r, g, b] = point.interpolated ? colorRampInterpolated(banded) : colorRamp(banded);
            const alphaBase = point.interpolated ? 0.2 : 0.6;
            const countBoost = Math.min(1, Math.sqrt(point.count || 1) / 6);
            const alpha = clamp01(alphaBase + countBoost * 0.2);
            const radius = Math.max(cellWidth, cellHeight) * (renderMode === "contour" ? 0.9 : spreadMultiplier);

            const x = point.cell_x * cellWidth + cellWidth / 2;
            const y = point.cell_y * cellHeight + cellHeight / 2;

            if (renderMode === "contour") {
                heatmapCtx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
                heatmapCtx.beginPath();
                heatmapCtx.arc(x, y, radius, 0, Math.PI * 2);
                heatmapCtx.fill();
            } else {
                const gradient = heatmapCtx.createRadialGradient(x, y, 0, x, y, radius);
                gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${alpha})`);
                gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
                heatmapCtx.fillStyle = gradient;
                heatmapCtx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
            }
        });

        if (confidenceToggle.checked) {
            const maxCount = Math.max(1, ...realPoints.map((point) => point.count || 1));
            realPoints.forEach((point) => {
                const confidence = clamp01((point.count || 1) / maxCount);
                const alpha = 0.35 * confidence;
                const x = point.cell_x * cellWidth;
                const y = point.cell_y * cellHeight;
                heatmapCtx.fillStyle = `rgba(17, 24, 39, ${alpha})`;
                heatmapCtx.fillRect(x, y, cellWidth, cellHeight);
            });
        }
    }

    function renderProviderOptions() {
        const modeProviders = cfg.serviceProviders?.[modeSelect.value] || [];
        const currentValue = providerSelect.value;
        providerSelect.innerHTML = "";

        const allOption = document.createElement("option");
        allOption.value = "all";
        allOption.textContent = "All";
        providerSelect.appendChild(allOption);

        modeProviders.forEach((provider) => {
            const option = document.createElement("option");
            option.value = provider;
            option.textContent = provider;
            providerSelect.appendChild(option);
        });

        providerSelect.value = modeProviders.includes(currentValue) || currentValue === "all" ? currentValue : "all";
    }

    async function refresh() {
        setMapImage();
        applyFloorDimensions();
        await waitForImageLoad();
        await loadHeatmap();
    }

    reloadBtn.addEventListener("click", refresh);
    blockSelect.addEventListener("change", function () {
        syncFloorOptions();
        refresh();
    });
    floorSelect.addEventListener("change", refresh);
    modeSelect.addEventListener("change", function () {
        renderProviderOptions();
        refresh();
    });
    providerSelect.addEventListener("change", refresh);
    renderModeSelect.addEventListener("change", refresh);
    interpolateToggle.addEventListener("change", refresh);
    autoSmoothToggle.addEventListener("change", refresh);
    confidenceToggle.addEventListener("change", refresh);
    spreadRange.addEventListener("input", refresh);
    window.addEventListener("resize", loadHeatmap);

    syncFloorOptions();
    renderProviderOptions();
    refresh();
})();
