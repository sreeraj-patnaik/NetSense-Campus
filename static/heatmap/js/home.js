(function () {
    const cfg = window.NETSENSE_CONFIG;
    const blockSelect = document.getElementById("blockSelect");
    const floorSelect = document.getElementById("floorSelect");
    const modeSelect = document.getElementById("modeSelect");
    const providerSelect = document.getElementById("providerSelect");
    const reloadBtn = document.getElementById("reloadBtn");
    const mapWrap = document.getElementById("mapWrap");
    const floorMap = document.getElementById("floorMap");
    const gridLayer = document.getElementById("gridLayer");
    const heatmapLayer = document.getElementById("heatmapLayer");
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

    function cellColor(signal) {
        if (signal >= -65) return "var(--strong)";
        if (signal >= -80) return "var(--medium)";
        return "var(--weak)";
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

    async function loadHeatmap() {
        if (!floorSelect.value) {
            heatmapLayer.innerHTML = "";
            return;
        }

        const params = new URLSearchParams({
            block: blockSelect.value,
            floor: floorSelect.value,
            mode: modeSelect.value,
        });
        if (providerSelect.value) {
            params.set("service_provider", providerSelect.value);
        }
        const url = `${cfg.heatmapApiUrl}?${params.toString()}`;

        heatmapLayer.innerHTML = "";
        const response = await fetch(url);
        const points = await response.json();
        if (!Array.isArray(points)) return;

        const mapRect = mapWrap.getBoundingClientRect();
        const cellWidth = mapRect.width / cols;
        const cellHeight = mapRect.height / rows;

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
    window.addEventListener("resize", loadHeatmap);

    syncFloorOptions();
    renderProviderOptions();
    refresh();
})();
