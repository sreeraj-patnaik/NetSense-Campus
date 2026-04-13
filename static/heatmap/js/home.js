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
    const weakClustersToggle = document.getElementById("weakClustersToggle");
    const bestProviderToggle = document.getElementById("bestProviderToggle");
    const spreadRange = document.getElementById("spreadRange");
    const legendMin = document.getElementById("legendMin");
    const legendMax = document.getElementById("legendMax");
    const legendAvg = document.getElementById("legendAvg");
    const legendStrong = document.getElementById("legendStrong");
    const legendWeak = document.getElementById("legendWeak");
    const autoRefreshToggle = document.getElementById("autoRefreshToggle");
    const refreshInterval = document.getElementById("refreshInterval");
    const exportBtn = document.getElementById("exportBtn");
    const notifyBtn = document.getElementById("notifyBtn");
    const mapWrap = document.getElementById("mapWrap");
    const mapStatus = document.getElementById("mapStatus");
    const floorMap = document.getElementById("floorMap");
    const gridLayer = document.getElementById("gridLayer");
    const heatmapCanvas = document.getElementById("heatmapCanvas");
    const heatmapCtx = heatmapCanvas.getContext("2d");
    const weakClusterTooltip = document.getElementById("weakClusterTooltip");
    let rows = cfg.rows;
    let cols = cfg.cols;
    let lastPoints = [];
    let refreshTimer = null;
    let weakClusters = [];
    let weakClusterLookup = new Map();
    let lastWeakClusterDigest = "";

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

    function hashString(value) {
        let hash = 0;
        const str = String(value || "");
        for (let i = 0; i < str.length; i += 1) {
            hash = (hash << 5) - hash + str.charCodeAt(i);
            hash |= 0;
        }
        return Math.abs(hash);
    }

    function providerColor(provider) {
        const colors = [
            [37, 99, 235],
            [16, 185, 129],
            [244, 63, 94],
            [245, 158, 11],
            [139, 92, 246],
            [20, 184, 166],
            [236, 72, 153],
        ];
        const idx = hashString(provider) % colors.length;
        return colors[idx];
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

    function syncMapAspectRatio() {
        if (!floorMap.naturalWidth || !floorMap.naturalHeight) return;
        mapWrap.style.setProperty("--map-aspect", `${floorMap.naturalWidth} / ${floorMap.naturalHeight}`);
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
                syncMapAspectRatio();
                resolve();
                return;
            }
            const onLoad = () => {
                floorMap.removeEventListener("load", onLoad);
                syncMapAspectRatio();
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

        if (mapStatus) {
            mapStatus.textContent = "Loading heatmap...";
        }
        mapWrap.classList.add("is-loading");

        const params = new URLSearchParams({
            block: blockSelect.value,
            floor: floorSelect.value,
            mode: modeSelect.value,
        });
        let url = "";
        if (bestProviderToggle?.checked) {
            url = `${cfg.bestProviderApiUrl}?${params.toString()}`;
        } else {
            params.set("interpolate", interpolateToggle.checked ? "1" : "0");
            if (providerSelect.value) {
                params.set("service_provider", providerSelect.value);
            }
            url = `${cfg.heatmapApiUrl}?${params.toString()}`;
        }

        let response = null;
        try {
            response = await fetch(url);
        } catch (error) {
            response = null;
        }

        if (!response) {
            if (mapStatus) {
                mapStatus.textContent = "Network error. Retrying...";
            }
            setTimeout(loadHeatmap, 2000);
            return;
        }

        if (!response.ok) {
            if (response.status === 401) {
                legendMin.textContent = "Login required";
                legendMax.textContent = "--";
                if (mapStatus) {
                    mapStatus.textContent = "Login required for heatmap.";
                }
                mapWrap.classList.remove("is-loading");
                return;
            }
            if (mapStatus) {
                mapStatus.textContent = "Unable to load heatmap.";
            }
            mapWrap.classList.remove("is-loading");
            return;
        }
        const raw = await response.json();
        const points = bestProviderToggle?.checked ? (raw?.cells || []) : raw;
        if (!Array.isArray(points)) {
            mapWrap.classList.remove("is-loading");
            return;
        }
        lastPoints = points;

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
        if (!scalePoints.length) {
            mapWrap.classList.remove("is-loading");
            return;
        }
        const signals = scalePoints.map((point) => point.signal);
        const minSignal = Math.min(...signals);
        const maxSignal = Math.max(...signals);
        const range = Math.max(1, maxSignal - minSignal);
        legendMin.textContent = `${minSignal.toFixed(1)} dBm`;
        legendMax.textContent = `${maxSignal.toFixed(1)} dBm`;
        if (legendAvg && legendStrong && legendWeak) {
            const avg = signals.reduce((acc, value) => acc + value, 0) / signals.length;
            const strong = signals.filter((value) => value >= -65).length;
            const weak = signals.filter((value) => value < -80).length;
            legendAvg.textContent = `${avg.toFixed(1)} dBm`;
            legendStrong.textContent = `${strong}`;
            legendWeak.textContent = `${weak}`;
        }

        const renderMode = renderModeSelect.value;
        const renderPoints = bestProviderToggle?.checked
            ? points
            : (interpolateToggle.checked ? points : points.filter((point) => !point.interpolated));
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
            let r = 0;
            let g = 0;
            let b = 0;
            if (bestProviderToggle?.checked) {
                [r, g, b] = providerColor(point.best_provider || "Unknown");
            } else {
                [r, g, b] = point.interpolated ? colorRampInterpolated(banded) : colorRamp(banded);
            }
            const alphaBase = point.interpolated ? 0.2 : 0.6;
            const countBoost = Math.min(1, Math.sqrt(point.count || 1) / 6);
            const confidence = clamp01(point.confidence ?? (bestProviderToggle?.checked ? 0.9 : 0.5));
            const alpha = clamp01((alphaBase + countBoost * 0.2) * (0.5 + 0.5 * confidence));
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

        if (confidenceToggle.checked && !bestProviderToggle?.checked) {
            realPoints.forEach((point) => {
                const confidence = clamp01(point.confidence ?? 0.5);
                const alpha = 0.45 * (1 - confidence);
                if (alpha <= 0) return;
                const x = point.cell_x * cellWidth;
                const y = point.cell_y * cellHeight;
                heatmapCtx.fillStyle = `rgba(120, 130, 140, ${alpha})`;
                heatmapCtx.fillRect(x, y, cellWidth, cellHeight);
            });
        }

        if (weakClustersToggle?.checked) {
            await loadWeakClusters();
            renderWeakClusters(cellWidth, cellHeight);
        } else {
            weakClusters = [];
            weakClusterLookup = new Map();
            hideWeakTooltip();
        }

        mapWrap.classList.remove("is-loading");
    }

    async function loadWeakClusters() {
        const params = new URLSearchParams({
            block: blockSelect.value,
            floor: floorSelect.value,
            mode: modeSelect.value,
        });
        if (providerSelect.value) {
            params.set("service_provider", providerSelect.value);
        }
        const url = `${cfg.weakClustersApiUrl}?${params.toString()}`;
        let response = null;
        try {
            response = await fetch(url);
        } catch (error) {
            response = null;
        }
        if (!response || !response.ok) {
            weakClusters = [];
            weakClusterLookup = new Map();
            return;
        }
        const payload = await response.json();
        weakClusters = Array.isArray(payload?.clusters) ? payload.clusters : [];
        weakClusterLookup = new Map();
        weakClusters.forEach((cluster, idx) => {
            (cluster.cells || []).forEach((cell) => {
                const key = `${cell[0]}:${cell[1]}`;
                weakClusterLookup.set(key, idx);
            });
        });
        maybeNotifyWeakClusters();
    }

    function renderWeakClusters(cellWidth, cellHeight) {
        weakClusters.forEach((cluster) => {
            (cluster.cells || []).forEach((cell) => {
                const cellX = Number(cell[0]);
                const cellY = Number(cell[1]);
                const x = cellX * cellWidth;
                const y = cellY * cellHeight;
                heatmapCtx.fillStyle = "rgba(239, 68, 68, 0.18)";
                heatmapCtx.fillRect(x, y, cellWidth, cellHeight);
                heatmapCtx.strokeStyle = "rgba(239, 68, 68, 0.85)";
                heatmapCtx.lineWidth = Math.max(1, Math.min(cellWidth, cellHeight) * 0.1);
                heatmapCtx.strokeRect(x + 1, y + 1, cellWidth - 2, cellHeight - 2);
            });
        });
    }

    function showWeakTooltip(text, left, top) {
        if (!weakClusterTooltip) return;
        weakClusterTooltip.textContent = text;
        weakClusterTooltip.style.left = `${left}px`;
        weakClusterTooltip.style.top = `${top}px`;
        weakClusterTooltip.hidden = false;
    }

    function hideWeakTooltip() {
        if (!weakClusterTooltip) return;
        weakClusterTooltip.hidden = true;
    }

    function maybeNotifyWeakClusters() {
        if (!window.NetSenseBridge || typeof window.NetSenseBridge.showNotification !== "function") {
            return;
        }
        const clusterCount = weakClusters.length;
        if (!clusterCount) {
            lastWeakClusterDigest = "";
            return;
        }
        const avgSignals = weakClusters.map((cluster) => cluster.avg_signal).join("|");
        const digest = `${blockSelect.value}:${floorSelect.value}:${modeSelect.value}:${clusterCount}:${avgSignals}`;
        if (digest === lastWeakClusterDigest) return;
        lastWeakClusterDigest = digest;
        window.NetSenseBridge.showNotification(
            "Weak zones detected",
            `${blockSelect.value} Floor ${floorSelect.value}: ${clusterCount} weak clusters`
        );
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

    function syncAutoRefresh() {
        if (!autoRefreshToggle || !refreshInterval) return;
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
        if (autoRefreshToggle.checked) {
            const interval = Math.max(5000, Number(refreshInterval.value || 30000));
            refreshTimer = setInterval(loadHeatmap, interval);
        }
    }

    async function subscribeToNotifications() {
        if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
            if (mapStatus) {
                mapStatus.textContent = "Notifications not supported in this browser.";
            }
            return;
        }
        if (!cfg.vapidPublicKey) {
            if (mapStatus) {
                mapStatus.textContent = "VAPID key missing. Add VAPID_PUBLIC_KEY in settings.";
            }
            return;
        }
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            if (mapStatus) {
                mapStatus.textContent = "Notification permission denied.";
            }
            return;
        }
        const registration = await navigator.serviceWorker.ready;
        const sub = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(cfg.vapidPublicKey),
        });
        await fetch(cfg.notificationSubscribeUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                subscription: sub.toJSON(),
                block: blockSelect.value,
                floor: floorSelect.value,
            }),
        });
        if (notifyBtn) {
            notifyBtn.textContent = "Notifications Enabled";
            notifyBtn.disabled = true;
        }
    }

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
        const rawData = atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    function exportPng() {
        if (!floorMap.complete || heatmapCanvas.width === 0) return;
        const exportCanvas = document.createElement("canvas");
        exportCanvas.width = heatmapCanvas.width;
        exportCanvas.height = heatmapCanvas.height;
        const ctx = exportCanvas.getContext("2d");
        ctx.drawImage(floorMap, 0, 0, exportCanvas.width, exportCanvas.height);
        ctx.drawImage(heatmapCanvas, 0, 0);
        ctx.strokeStyle = "rgba(16, 32, 64, 0.22)";
        ctx.lineWidth = 1;
        for (let i = 1; i < cols; i += 1) {
            const x = (exportCanvas.width / cols) * i;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, exportCanvas.height);
            ctx.stroke();
        }
        for (let j = 1; j < rows; j += 1) {
            const y = (exportCanvas.height / rows) * j;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(exportCanvas.width, y);
            ctx.stroke();
        }
        const link = document.createElement("a");
        link.download = `heatmap-${blockSelect.value}-floor-${floorSelect.value}.png`;
        link.href = exportCanvas.toDataURL("image/png");
        link.click();
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
    weakClustersToggle?.addEventListener("change", refresh);
    bestProviderToggle?.addEventListener("change", function () {
        providerSelect.disabled = bestProviderToggle.checked;
        interpolateToggle.disabled = bestProviderToggle.checked;
        confidenceToggle.disabled = bestProviderToggle.checked;
        refresh();
    });
    spreadRange.addEventListener("input", refresh);
    autoRefreshToggle?.addEventListener("change", syncAutoRefresh);
    refreshInterval?.addEventListener("change", syncAutoRefresh);
    exportBtn?.addEventListener("click", exportPng);
    notifyBtn?.addEventListener("click", subscribeToNotifications);
    window.addEventListener("resize", loadHeatmap);
    mapWrap.addEventListener("mouseleave", hideWeakTooltip);
    mapWrap.addEventListener("mousemove", function (event) {
        if (!weakClustersToggle?.checked || !weakClusterLookup.size) {
            hideWeakTooltip();
            return;
        }
        const rect = mapWrap.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const cellWidth = rect.width / cols;
        const cellHeight = rect.height / rows;
        const cellX = Math.max(0, Math.min(cols - 1, Math.floor(x / cellWidth)));
        const cellY = Math.max(0, Math.min(rows - 1, Math.floor(y / cellHeight)));
        const key = `${cellX}:${cellY}`;
        if (!weakClusterLookup.has(key)) {
            hideWeakTooltip();
            return;
        }
        const cluster = weakClusters[weakClusterLookup.get(key)];
        const text = `Weak zone: ${cluster.size} cells, avg ${cluster.avg_signal} dBm`;
        showWeakTooltip(text, x + 12, y + 12);
    });

    syncFloorOptions();
    renderProviderOptions();
    syncAutoRefresh();
    if (bestProviderToggle?.checked) {
        providerSelect.disabled = true;
        interpolateToggle.disabled = true;
        confidenceToggle.disabled = true;
    }
    if (notifyBtn && "Notification" in window && Notification.permission === "granted") {
        notifyBtn.textContent = "Notifications Enabled";
        notifyBtn.disabled = true;
    }
    refresh();
})();
