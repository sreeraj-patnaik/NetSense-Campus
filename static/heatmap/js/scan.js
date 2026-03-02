(function () {
    const cfg = window.NETSENSE_SCAN_CONFIG;
    const mapWrap = document.getElementById("scanMapWrap");
    const floorMap = document.getElementById("scanFloorMap");
    const blockSelect = document.getElementById("scanBlock");
    const floorSelect = document.getElementById("scanFloor");
    const modeSelect = document.getElementById("scanMode");
    const providerSelect = document.getElementById("serviceProviderSelect");
    const networkNameInput = document.getElementById("networkNameInput");
    const gridLayer = document.getElementById("scanGridLayer");
    const markerLayer = document.getElementById("scanMarkerLayer");
    const cellXInput = document.getElementById("cellXInput");
    const cellYInput = document.getElementById("cellYInput");
    const selectedCellText = document.getElementById("selectedCellText");
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

    function modeProviders(mode) {
        return cfg.serviceProviders?.[mode] || [];
    }

    function drawGrid() {
        const colStep = 100 / cols;
        const rowStep = 100 / rows;
        gridLayer.style.backgroundImage = [
            `repeating-linear-gradient(to right, rgba(16,32,64,0.32), rgba(16,32,64,0.32) 1px, transparent 1px, transparent ${colStep}%)`,
            `repeating-linear-gradient(to bottom, rgba(16,32,64,0.32), rgba(16,32,64,0.32) 1px, transparent 1px, transparent ${rowStep}%)`,
        ].join(",");
    }

    function setMapImage() {
        const floorCfg = selectedFloorConfig();
        floorMap.src = floorCfg.image_url || cfg.defaultFloorImage;
    }

    function drawSelectedCell(cellX, cellY) {
        markerLayer.innerHTML = "";
        const rect = mapWrap.getBoundingClientRect();
        const cellWidth = rect.width / cols;
        const cellHeight = rect.height / rows;
        const marker = document.createElement("div");
        marker.style.position = "absolute";
        marker.style.left = `${cellX * cellWidth}px`;
        marker.style.top = `${cellY * cellHeight}px`;
        marker.style.width = `${cellWidth}px`;
        marker.style.height = `${cellHeight}px`;
        marker.style.border = "2px solid #165ba8";
        marker.style.background = "rgba(22,91,168,0.20)";
        markerLayer.appendChild(marker);
    }

    function clearSelectedCell() {
        cellXInput.value = "";
        cellYInput.value = "";
        selectedCellText.textContent = "None";
        markerLayer.innerHTML = "";
    }

    function applyFloorDimensions() {
        const floorCfg = selectedFloorConfig();
        rows = Math.max(1, Number(floorCfg.rows || cfg.rows));
        cols = Math.max(1, Number(floorCfg.cols || cfg.cols));
        mapWrap.dataset.rows = String(rows);
        mapWrap.dataset.cols = String(cols);
        clearSelectedCell();
        drawGrid();
    }

    function updateNetworkLabel() {
        if (modeSelect.value === "wifi") {
            networkNameInput.placeholder = "CampusNet-2F-AP01";
        } else {
            networkNameInput.placeholder = "Carrier profile (optional)";
        }
    }

    function renderProviderOptions() {
        const providers = modeProviders(modeSelect.value);
        const currentValue = providerSelect.value;
        providerSelect.innerHTML = "";

        providers.forEach((provider) => {
            const option = document.createElement("option");
            option.value = provider;
            option.textContent = provider;
            providerSelect.appendChild(option);
        });

        if (providers.length === 0) {
            const option = document.createElement("option");
            option.value = "Unknown";
            option.textContent = "Unknown";
            providerSelect.appendChild(option);
        }

        if (providers.includes(currentValue)) {
            providerSelect.value = currentValue;
        } else {
            providerSelect.selectedIndex = 0;
        }
    }

    mapWrap.addEventListener("click", function (event) {
        if (!floorSelect.value) return;
        const rect = mapWrap.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const cellWidth = rect.width / cols;
        const cellHeight = rect.height / rows;
        const cellX = Math.max(0, Math.min(cols - 1, Math.floor(x / cellWidth)));
        const cellY = Math.max(0, Math.min(rows - 1, Math.floor(y / cellHeight)));

        cellXInput.value = cellX;
        cellYInput.value = cellY;
        selectedCellText.textContent = `${cellX}, ${cellY}`;
        drawSelectedCell(cellX, cellY);
    });

    blockSelect.addEventListener("change", function () {
        syncFloorOptions();
        setMapImage();
        applyFloorDimensions();
    });
    floorSelect.addEventListener("change", function () {
        setMapImage();
        applyFloorDimensions();
    });
    modeSelect.addEventListener("change", function () {
        renderProviderOptions();
        updateNetworkLabel();
    });
    window.addEventListener("resize", function () {
        if (cellXInput.value !== "" && cellYInput.value !== "") {
            drawSelectedCell(Number(cellXInput.value), Number(cellYInput.value));
        }
    });

    syncFloorOptions();
    setMapImage();
    renderProviderOptions();
    updateNetworkLabel();
    applyFloorDimensions();
})();
