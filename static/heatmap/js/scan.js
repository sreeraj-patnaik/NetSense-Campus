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
    const suggestScanBtn = document.getElementById("suggestScanBtn");
    const autoScanStatus = document.getElementById("autoScanStatus");
    const autoScanDebug = document.getElementById("autoScanDebug");
    const suggestScanStatus = document.getElementById("suggestScanStatus");
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
        if (floorMap.complete && floorMap.naturalWidth > 0) {
            syncMapAspectRatio();
            applyOverlayFrame();
        }
    }

    function syncMapAspectRatio() {
        if (!floorMap.naturalWidth || !floorMap.naturalHeight) return;
        mapWrap.style.setProperty("--map-aspect", `${floorMap.naturalWidth} / ${floorMap.naturalHeight}`);
    }

    function getRenderedImageFrame() {
        const wrapRect = mapWrap.getBoundingClientRect();
        if (!floorMap.naturalWidth || !floorMap.naturalHeight || !wrapRect.width || !wrapRect.height) {
            return {
                left: 0,
                top: 0,
                width: wrapRect.width,
                height: wrapRect.height,
            };
        }

        const scale = Math.min(
            wrapRect.width / floorMap.naturalWidth,
            wrapRect.height / floorMap.naturalHeight
        );
        const width = Math.max(1, floorMap.naturalWidth * scale);
        const height = Math.max(1, floorMap.naturalHeight * scale);

        return {
            left: (wrapRect.width - width) / 2,
            top: (wrapRect.height - height) / 2,
            width,
            height,
        };
    }

    function applyOverlayFrame() {
        const frame = getRenderedImageFrame();
        [gridLayer, markerLayer].forEach((layer) => {
            layer.style.left = `${frame.left}px`;
            layer.style.top = `${frame.top}px`;
            layer.style.width = `${frame.width}px`;
            layer.style.height = `${frame.height}px`;
        });
    }

    function drawSelectedCell(cellX, cellY) {
        const existing = markerLayer.querySelector(".selected-marker");
        if (existing) {
            existing.remove();
        }
        const frame = getRenderedImageFrame();
        const cellWidth = frame.width / cols;
        const cellHeight = frame.height / rows;
        const marker = document.createElement("div");
        marker.className = "selected-marker";
        marker.style.position = "absolute";
        marker.style.left = `${cellX * cellWidth}px`;
        marker.style.top = `${cellY * cellHeight}px`;
        marker.style.width = `${cellWidth}px`;
        marker.style.height = `${cellHeight}px`;
        marker.style.border = "2px solid #165ba8";
        marker.style.background = "rgba(22,91,168,0.20)";
        markerLayer.appendChild(marker);
    }

    function drawSuggestedCell(cellX, cellY) {
        const existing = markerLayer.querySelector(".suggested-marker");
        if (existing) {
            existing.remove();
        }
        const frame = getRenderedImageFrame();
        const cellWidth = frame.width / cols;
        const cellHeight = frame.height / rows;
        const marker = document.createElement("div");
        marker.className = "suggested-marker";
        marker.style.position = "absolute";
        marker.style.left = `${cellX * cellWidth}px`;
        marker.style.top = `${cellY * cellHeight}px`;
        marker.style.width = `${cellWidth}px`;
        marker.style.height = `${cellHeight}px`;
        marker.style.border = "2px dashed #f59e0b";
        marker.style.background = "rgba(245,158,11,0.12)";
        marker.dataset.cellX = String(cellX);
        marker.dataset.cellY = String(cellY);
        markerLayer.appendChild(marker);
    }

    function clearSelectedCell() {
        cellXInput.value = "";
        cellYInput.value = "";
        selectedCellText.textContent = "No spot selected";
        const selectedMarker = markerLayer.querySelector(".selected-marker");
        if (selectedMarker) {
            selectedMarker.remove();
        }
    }

    function clearSuggestedCell() {
        const suggestedMarker = markerLayer.querySelector(".suggested-marker");
        if (suggestedMarker) {
            suggestedMarker.remove();
        }
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
        clearSuggestedCell();
        drawGrid();
        applyOverlayFrame();
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
        const wrapRect = mapWrap.getBoundingClientRect();
        const frame = getRenderedImageFrame();
        const x = event.clientX - wrapRect.left - frame.left;
        const y = event.clientY - wrapRect.top - frame.top;
        if (x < 0 || y < 0 || x > frame.width || y > frame.height) {
            return;
        }
        const cellWidth = frame.width / cols;
        const cellHeight = frame.height / rows;
        const cellX = Math.max(0, Math.min(cols - 1, Math.floor(x / cellWidth)));
        const cellY = Math.max(0, Math.min(rows - 1, Math.floor(y / cellHeight)));

        if (isBlockedCell(cellX, cellY)) {
            clearSelectedCell();
            selectedCellText.textContent = "That spot is unavailable";
            return;
        }

        clearSuggestedCell();
        cellXInput.value = cellX;
        cellYInput.value = cellY;
        selectedCellText.textContent = "Spot selected";
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
        clearSuggestedCell();
    });
    window.addEventListener("resize", function () {
        syncMapAspectRatio();
        applyOverlayFrame();
        if (cellXInput.value !== "" && cellYInput.value !== "") {
            drawSelectedCell(Number(cellXInput.value), Number(cellYInput.value));
        }
        const suggestedMarker = markerLayer.querySelector(".suggested-marker");
        if (suggestedMarker) {
            const cellX = Number(suggestedMarker.dataset.cellX || 0);
            const cellY = Number(suggestedMarker.dataset.cellY || 0);
            drawSuggestedCell(cellX, cellY);
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

    function setSuggestStatus(message, tone) {
        if (!suggestScanStatus) return;
        suggestScanStatus.textContent = message;
        suggestScanStatus.dataset.tone = tone || "info";
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
            setAutoScanStatus("Reading device details...", "info");
            if (window.NetSenseBridge && typeof window.NetSenseBridge.getNetworkInfo === "function") {
                try {
                    const raw = window.NetSenseBridge.getNetworkInfo();
                    setAutoScanDebug(`Bridge response: ${raw}`);
                    const info = JSON.parse(raw || "{}");
                    if (info.error === "permission") {
                        setAutoScanStatus("Allow the requested permission, then try again.", "warning");
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
                        setAutoScanStatus("Device details filled in.", "success");
                    } else {
                        setAutoScanStatus("Network detected, but the reading value is missing.", "warning");
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
                        ? "Wi-Fi detected. Add any missing details."
                        : "Mobile signal detected. Add any missing details.",
                    "success"
                );
            } else {
                setAutoScanStatus("Auto fill is not available here. Enter the details manually.", "warning");
                setAutoScanDebug("Device bridge not available in this browser.");
            }
        });
    }

    if (suggestScanBtn) {
        suggestScanBtn.addEventListener("click", async function () {
            if (!cfg.nextScanApiUrl) {
                setSuggestStatus("Next scan API not configured.", "warning");
                return;
            }
            if (!blockSelect.value || !floorSelect.value) {
                setSuggestStatus("Select a block and floor first.", "warning");
                return;
            }

            setSuggestStatus("Finding next best cell...", "info");
            const params = new URLSearchParams({
                block: blockSelect.value,
                floor: floorSelect.value,
                mode: modeSelect.value,
            });
            if (providerInput.value) {
                params.set("service_provider", providerInput.value);
            }

            let response = null;
            try {
                response = await fetch(`${cfg.nextScanApiUrl}?${params.toString()}`);
            } catch (error) {
                response = null;
            }

            if (!response || !response.ok) {
                setSuggestStatus("Unable to fetch suggestion.", "warning");
                return;
            }

            const data = await response.json();
            if (data.cell_x === undefined || data.cell_y === undefined) {
                setSuggestStatus("No suggestion available.", "warning");
                return;
            }

            const cellX = Number(data.cell_x);
            const cellY = Number(data.cell_y);
            clearSuggestedCell();
            drawSuggestedCell(cellX, cellY);
            cellXInput.value = cellX;
            cellYInput.value = cellY;
            selectedCellText.textContent = "Suggested spot selected";
            drawSelectedCell(cellX, cellY);
            setSuggestStatus("Suggested spot added.", "success");
        });
    }

    syncFloorOptions();
    setMapImage();
    floorMap.addEventListener("load", function () {
        syncMapAspectRatio();
        applyOverlayFrame();
    });
    renderProviderOptions();
    updateNetworkLabel();
    applyFloorDimensions();
    applyOverlayFrame();

    if (autoScanStatus && window.NetSenseBridge && typeof window.NetSenseBridge.getNetworkInfo === "function") {
        setAutoScanStatus("Device fill is ready. Tap Fill from device.", "info");
        setAutoScanDebug("Device bridge detected.");
    } else {
        setAutoScanDebug("Device bridge not detected on load.");
    }
})();
