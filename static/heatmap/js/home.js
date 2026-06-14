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
    const trendChart = document.getElementById("trendChart");
    const trendCtx = trendChart ? trendChart.getContext("2d") : null;
    const alertsList = document.getElementById("alertsList");
    const compareBlock = document.getElementById("compareBlock");
    const compareFloor = document.getElementById("compareFloor");
    const compareRefreshBtn = document.getElementById("compareRefreshBtn");
    const compareCurrentLabel = document.getElementById("compareCurrentLabel");
    const compareCurrentSignal = document.getElementById("compareCurrentSignal");
    const compareCurrentWeak = document.getElementById("compareCurrentWeak");
    const compareCurrentConfidence = document.getElementById("compareCurrentConfidence");
    const compareTargetLabel = document.getElementById("compareTargetLabel");
    const compareTargetSignal = document.getElementById("compareTargetSignal");
    const compareTargetWeak = document.getElementById("compareTargetWeak");
    const compareTargetConfidence = document.getElementById("compareTargetConfidence");
    const trendAvg = document.getElementById("trendAvg");
    const trendMin = document.getElementById("trendMin");
    const trendMax = document.getElementById("trendMax");
    const trendCount = document.getElementById("trendCount");
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
    let dashboardInsights = null;

    function selectedKey() {
        return `${blockSelect.value}:${floorSelect.value}`;
    }

    function selectedFloorConfig() {
        return cfg.floorConfigs?.[selectedKey()] || {};
    }

    function floorsForBlock(block) {
        return cfg.blockFloors?.[block] || [];
    }

    function selectedPreset() {
        return String(cfg.selectedPreset || "my_institution");
    }

    function syncCompareFloors() {
        if (!compareBlock || !compareFloor) return;
        const floors = floorsForBlock(compareBlock.value);
        const currentValue = compareFloor.value || String(cfg.compareFloor || "");
        compareFloor.innerHTML = "";

        floors.forEach((floor) => {
            const option = document.createElement("option");
            option.value = String(floor);
            option.textContent = String(floor);
            compareFloor.appendChild(option);
        });

        if (!floors.length) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No floors";
            compareFloor.appendChild(option);
            compareFloor.disabled = true;
            return;
        }

        compareFloor.disabled = false;
        compareFloor.value = floors.map(String).includes(currentValue) ? currentValue : String(floors[0]);
    }

    function setPresetDefaults() {
        const preset = selectedPreset();
        if (preset === "best_provider" && bestProviderToggle) {
            bestProviderToggle.checked = true;
            providerSelect.disabled = true;
            interpolateToggle.disabled = true;
            confidenceToggle.disabled = true;
        }
        if (preset === "weak_zones" && weakClustersToggle) {
            weakClustersToggle.checked = true;
        }
    }

    function fmtNumber(value, digits = 1) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) {
            return "--";
        }
        return Number(value).toFixed(digits);
    }

    function setText(idNode, value) {
        if (idNode) idNode.textContent = value;
    }

    function renderAlerts(alerts) {
        if (!alertsList) return;
        alertsList.innerHTML = "";
        if (!alerts || !alerts.length) {
            const empty = document.createElement("div");
            empty.className = "muted";
            empty.textContent = "No updates for this view right now.";
            alertsList.appendChild(empty);
            return;
        }

        alerts.forEach((alert) => {
            const card = document.createElement("div");
            card.className = `alert-card tone-${alert.tone || "info"}`;
            const title = document.createElement("strong");
            title.textContent = alert.title || "Alert";
            const message = document.createElement("p");
            message.textContent = alert.message || "";
            card.appendChild(title);
            card.appendChild(message);
            alertsList.appendChild(card);
        });
    }

    function renderTrendChart(points) {
        if (!trendChart || !trendCtx) return;
        const rect = trendChart.getBoundingClientRect();
        const width = Math.max(1, Math.floor(rect.width));
        const height = Math.max(1, Math.floor(Math.max(220, rect.height || 240)));
        trendChart.width = width;
        trendChart.height = height;
        trendCtx.clearRect(0, 0, width, height);

        if (!points || !points.length) {
            trendCtx.fillStyle = "rgba(16,32,64,0.45)";
            trendCtx.font = "600 14px Inter, sans-serif";
            trendCtx.fillText("No coverage data yet.", 20, 30);
            return;
        }

        const validSignals = points.filter((point) => point.avg_signal !== null && point.avg_signal !== undefined);
        if (!validSignals.length) {
            trendCtx.fillStyle = "rgba(16,32,64,0.45)";
            trendCtx.font = "600 14px Inter, sans-serif";
            trendCtx.fillText("No coverage data yet.", 20, 30);
            return;
        }

        const values = validSignals.map((point) => Number(point.avg_signal));
        const minSignal = Math.min(...values);
        const maxSignal = Math.max(...values);
        const range = Math.max(1, maxSignal - minSignal);
        const padX = 22;
        const padY = 28;
        const plotWidth = width - padX * 2;
        const plotHeight = height - padY * 2;

        trendCtx.strokeStyle = "rgba(109, 127, 167, 0.18)";
        trendCtx.lineWidth = 1;
        for (let i = 0; i < 4; i += 1) {
            const y = padY + (plotHeight / 3) * i;
            trendCtx.beginPath();
            trendCtx.moveTo(padX, y);
            trendCtx.lineTo(width - padX, y);
            trendCtx.stroke();
        }

        trendCtx.strokeStyle = "rgba(111, 73, 217, 0.92)";
        trendCtx.lineWidth = 3;
        trendCtx.beginPath();
        points.forEach((point, index) => {
            const x = padX + (plotWidth * index) / Math.max(1, points.length - 1);
            const signal = point.avg_signal !== null && point.avg_signal !== undefined ? Number(point.avg_signal) : minSignal;
            const normalized = (signal - minSignal) / range;
            const y = padY + plotHeight - normalized * plotHeight;
            if (index === 0) {
                trendCtx.moveTo(x, y);
            } else {
                trendCtx.lineTo(x, y);
            }
        });
        trendCtx.stroke();

        points.forEach((point, index) => {
            const x = padX + (plotWidth * index) / Math.max(1, points.length - 1);
            const signal = point.avg_signal !== null && point.avg_signal !== undefined ? Number(point.avg_signal) : minSignal;
            const normalized = (signal - minSignal) / range;
            const y = padY + plotHeight - normalized * plotHeight;
            trendCtx.fillStyle = "rgba(244,131,4,0.95)";
            trendCtx.beginPath();
            trendCtx.arc(x, y, 4, 0, Math.PI * 2);
            trendCtx.fill();
        });
    }

    function renderComparison(comparison) {
        if (!comparison) return;
        const current = comparison.current || {};
        const target = comparison.comparison || {};
        if (compareCurrentLabel) compareCurrentLabel.textContent = `${current.block || "--"} - F${current.floor ?? "--"}`;
        if (compareCurrentSignal) compareCurrentSignal.textContent = current.avg_signal === null || current.avg_signal === undefined ? "--" : `${fmtNumber(current.avg_signal)} dBm`;
        if (compareCurrentWeak) compareCurrentWeak.textContent = current.weak_cells ?? "--";
        if (compareCurrentConfidence) compareCurrentConfidence.textContent = current.avg_confidence === null || current.avg_confidence === undefined ? "--" : fmtNumber(current.avg_confidence, 3);
        if (compareTargetLabel) compareTargetLabel.textContent = `${target.block || "--"} - F${target.floor ?? "--"}`;
        if (compareTargetSignal) compareTargetSignal.textContent = target.avg_signal === null || target.avg_signal === undefined ? "--" : `${fmtNumber(target.avg_signal)} dBm`;
        if (compareTargetWeak) compareTargetWeak.textContent = target.weak_cells ?? "--";
        if (compareTargetConfidence) compareTargetConfidence.textContent = target.avg_confidence === null || target.avg_confidence === undefined ? "--" : fmtNumber(target.avg_confidence, 3);
    }

    async function loadDashboardInsights() {
        if (!cfg.dashboardInsightsApiUrl || !blockSelect.value || !floorSelect.value) return;
        const params = new URLSearchParams({
            block: blockSelect.value,
            floor: floorSelect.value,
            mode: modeSelect.value,
            weak_threshold: String(cfg.weakThreshold || -80),
        });
        if (providerSelect.value) {
            params.set("service_provider", providerSelect.value);
        }
        if (compareBlock?.value) {
            params.set("compare_block", compareBlock.value);
        }
        if (compareFloor?.value) {
            params.set("compare_floor", compareFloor.value);
        }
        let response = null;
        try {
            response = await fetch(`${cfg.dashboardInsightsApiUrl}?${params.toString()}`);
        } catch (error) {
            response = null;
        }
        if (!response || !response.ok) {
            return;
        }
        dashboardInsights = await response.json();
        const trend = dashboardInsights?.trend || {};
        const summary = trend.summary || {};
        const points = trend.points || [];
        renderTrendChart(points);
        renderAlerts(dashboardInsights?.alerts?.alerts || []);
        renderComparison(dashboardInsights?.comparison || {});
        if (trendAvg) trendAvg.textContent = summary.avg_signal === null || summary.avg_signal === undefined ? "--" : `${fmtNumber(summary.avg_signal)} dBm`;
        if (trendMin) trendMin.textContent = summary.min_signal === null || summary.min_signal === undefined ? "--" : `${fmtNumber(summary.min_signal)} dBm`;
        if (trendMax) trendMax.textContent = summary.max_signal === null || summary.max_signal === undefined ? "--" : `${fmtNumber(summary.max_signal)} dBm`;
        if (trendCount) trendCount.textContent = summary.total_scans ?? "--";
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
        floorMap.src = floorCfg.image_url || cfg.defaultFloorImage || "";
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
        [gridLayer, heatmapCanvas].forEach((layer) => {
            layer.style.left = `${frame.left}px`;
            layer.style.top = `${frame.top}px`;
            layer.style.width = `${frame.width}px`;
            layer.style.height = `${frame.height}px`;
        });
    }

    function applyFloorDimensions() {
        const floorCfg = selectedFloorConfig();
        rows = Math.max(1, Number(floorCfg.rows || cfg.rows));
        cols = Math.max(1, Number(floorCfg.cols || cfg.cols));
        mapWrap.dataset.rows = String(rows);
        mapWrap.dataset.cols = String(cols);
        drawGrid();
        applyOverlayFrame();
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
            if (mapStatus && cfg.accessStatus && cfg.accessStatus !== "approved") {
                mapStatus.textContent = "Access pending approval.";
                mapWrap.classList.add("is-loading");
            }
            return;
        }

        if (mapStatus) {
            mapStatus.textContent = "Loading coverage...";
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
                legendMin.textContent = "Sign in";
                legendMax.textContent = "--";
                if (mapStatus) {
                    mapStatus.textContent = "Sign in to view coverage.";
                }
                mapWrap.classList.remove("is-loading");
                return;
            }
            if (response.status === 403) {
                if (mapStatus) {
                    mapStatus.textContent = "This workspace is not available to you.";
                }
                mapWrap.classList.remove("is-loading");
                return;
            }
                if (mapStatus) {
                    mapStatus.textContent = "Unable to load coverage.";
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

        const frame = getRenderedImageFrame();
        if (!frame.width || !frame.height) {
            requestAnimationFrame(loadHeatmap);
            return;
        }
        const cellWidth = frame.width / cols;
        const cellHeight = frame.height / rows;
        const canvasWidth = Math.max(1, Math.floor(frame.width));
        const canvasHeight = Math.max(1, Math.floor(frame.height));
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
        await loadDashboardInsights();
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
    compareBlock?.addEventListener("change", function () {
        syncCompareFloors();
        loadDashboardInsights();
    });
    compareFloor?.addEventListener("change", loadDashboardInsights);
    compareRefreshBtn?.addEventListener("click", loadDashboardInsights);
    window.addEventListener("resize", loadHeatmap);
    mapWrap.addEventListener("mouseleave", hideWeakTooltip);
    mapWrap.addEventListener("mousemove", function (event) {
        if (!weakClustersToggle?.checked || !weakClusterLookup.size) {
            hideWeakTooltip();
            return;
        }
        const wrapRect = mapWrap.getBoundingClientRect();
        const frame = getRenderedImageFrame();
        const x = event.clientX - wrapRect.left - frame.left;
        const y = event.clientY - wrapRect.top - frame.top;
        if (x < 0 || y < 0 || x > frame.width || y > frame.height) {
            hideWeakTooltip();
            return;
        }
        const cellWidth = frame.width / cols;
        const cellHeight = frame.height / rows;
        const cellX = Math.max(0, Math.min(cols - 1, Math.floor(x / cellWidth)));
        const cellY = Math.max(0, Math.min(rows - 1, Math.floor(y / cellHeight)));
        const key = `${cellX}:${cellY}`;
        if (!weakClusterLookup.has(key)) {
            hideWeakTooltip();
            return;
        }
        const cluster = weakClusters[weakClusterLookup.get(key)];
        const text = `Weak zone: ${cluster.size} cells, avg ${cluster.avg_signal} dBm`;
        showWeakTooltip(text, frame.left + x + 12, frame.top + y + 12);
    });

    syncFloorOptions();
    renderProviderOptions();
    syncCompareFloors();
    setPresetDefaults();
    syncAutoRefresh();
    if (bestProviderToggle?.checked) {
        providerSelect.disabled = true;
        interpolateToggle.disabled = true;
        confidenceToggle.disabled = true;
    }
    applyOverlayFrame();
    refresh();
})();
