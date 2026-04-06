(function () {
    const cfg = window.NETSENSE_SCAN_CONFIG;
    const mapWrap = document.getElementById("scanMapWrap");
    const floorMap = document.getElementById("scanFloorMap");
    const blockSelect = document.getElementById("scanBlock");
    const floorSelect = document.getElementById("scanFloor");
    const modeSelect = document.getElementById("scanMode");
    const providerInput = document.getElementById("serviceProviderInput");
    const providerList = document.getElementById("serviceProviderList");
    const networkNameInput = document.getElementById("networkNameInput");
    const signalStrengthInput = document.getElementById("signalStrengthInput");
    const gridLayer = document.getElementById("scanGridLayer");
    const markerLayer = document.getElementById("scanMarkerLayer");
    const cellXInput = document.getElementById("cellXInput");
    const cellYInput = document.getElementById("cellYInput");
    const selectedCellText = document.getElementById("selectedCellText");
    const autoScanBtn = document.getElementById("autoScanBtn");
    const autoScanStatus = document.getElementById("autoScanStatus");
    const autoScanDebug = document.getElementById("autoScanDebug");
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

    function isBlockedCell(cellX, cellY) {
        const floorCfg = selectedFloorConfig();
        const blockedCells = new Set(floorCfg.blocked_cells || []);
        if (!blockedCells.size) return false;
        const cellId = cellY * cols + cellX;
        return blockedCells.has(cellId);
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
        const currentValue = providerInput.value;
        providerList.innerHTML = "";

        providers.forEach((provider) => {
            const option = document.createElement("option");
            option.value = provider;
            providerList.appendChild(option);
        });

        if (!currentValue && providers.length) {
            providerInput.value = providers[0];
        }
        if (!providers.length && !providerInput.value) {
            providerInput.value = "Unknown";
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

        if (isBlockedCell(cellX, cellY)) {
            clearSelectedCell();
            selectedCellText.textContent = "Blocked cell";
            return;
        }

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

    function setAutoScanStatus(message, tone) {
        if (!autoScanStatus) return;
        autoScanStatus.textContent = message;
        autoScanStatus.dataset.tone = tone || "info";
    }

    function setAutoScanDebug(message) {
        if (!autoScanDebug) return;
        autoScanDebug.textContent = message;
        autoScanDebug.hidden = !message;
    }

    function inferNetworkMode() {
        const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (!connection) return null;
        const rawType = connection.type || connection.effectiveType || "";
        const type = String(rawType).toLowerCase();
        if (type.includes("wifi") || type.includes("ethernet")) return "wifi";
        if (type.includes("cellular")) return "mobile";
        if (["slow-2g", "2g", "3g", "4g", "5g"].includes(type)) return "mobile";
        return null;
    }

    if (autoScanBtn) {
        autoScanBtn.addEventListener("click", function () {
            setAutoScanStatus("Scanning device network...", "info");
            if (window.NetSenseBridge && typeof window.NetSenseBridge.getNetworkInfo === "function") {
                try {
                    const raw = window.NetSenseBridge.getNetworkInfo();
                    setAutoScanDebug(`Bridge response: ${raw}`);
                    const info = JSON.parse(raw || "{}");
                    if (info.error === "permission") {
                        setAutoScanStatus("Allow Location permission to read dBm/SSID, then retry.", "warning");
                        return;
                    }
                    if (info.mode) {
                        modeSelect.value = info.mode;
                    }
                    renderProviderOptions();
                    updateNetworkLabel();
                    if (info.provider) {
                        providerInput.value = info.provider;
                    } else if (!providerInput.value) {
                        providerInput.value = "Unknown";
                    }
                    if (info.ssid && networkNameInput && modeSelect.value === "wifi") {
                        networkNameInput.value = info.ssid;
                    }
                    if (signalStrengthInput && info.dbm !== undefined && info.dbm !== "") {
                        signalStrengthInput.value = info.dbm;
                    }
                    if (info.dbm !== undefined && info.dbm !== "") {
                        setAutoScanStatus("Auto scan populated from device network.", "success");
                    } else {
                        setAutoScanStatus("Network detected, but dBm unavailable. Check permissions.", "warning");
                    }
                    return;
                } catch (error) {
                    console.warn("Auto scan bridge failed", error);
                    setAutoScanDebug(`Bridge error: ${error}`);
                }
            }

            const inferred = inferNetworkMode();
            if (inferred) {
                modeSelect.value = inferred;
                renderProviderOptions();
                updateNetworkLabel();
                if (!providerInput.value) {
                    providerInput.value = "Unknown";
                }
                setAutoScanStatus(
                    inferred === "wifi"
                        ? "Wi-Fi detected. Enter SSID/provider if missing."
                        : "Mobile data detected. Enter carrier if missing.",
                    "success"
                );
            } else {
                setAutoScanStatus("Auto detect not supported on this browser. Pick mode manually.", "warning");
                setAutoScanDebug("Bridge missing. Window.NetSenseBridge not found.");
            }
        });
    }

    syncFloorOptions();
    setMapImage();
    renderProviderOptions();
    updateNetworkLabel();
    applyFloorDimensions();

    if (autoScanStatus && window.NetSenseBridge && typeof window.NetSenseBridge.getNetworkInfo === "function") {
        setAutoScanStatus("Native auto scan ready. Tap Auto Scan.", "info");
        setAutoScanDebug("Bridge detected.");
    } else {
        setAutoScanDebug("Bridge missing on load. If using APK, reinstall latest build.");
    }
})();
