(function () {
    const cfg = window.NETSENSE_SCAN_CONFIG;
    const mapWrap = document.getElementById("scanMapWrap");
    const floorMap = document.getElementById("scanFloorMap");
    const blockSelect = document.getElementById("scanBlock");
    const floorSelect = document.getElementById("scanFloor");
    const gridLayer = document.getElementById("scanGridLayer");
    const markerLayer = document.getElementById("scanMarkerLayer");
    const cellXInput = document.getElementById("cellXInput");
    const cellYInput = document.getElementById("cellYInput");
    const selectedCellText = document.getElementById("selectedCellText");

    function drawGrid() {
        const colStep = 100 / cfg.cols;
        const rowStep = 100 / cfg.rows;
        gridLayer.style.backgroundImage = [
            `repeating-linear-gradient(to right, rgba(16,32,64,0.32), rgba(16,32,64,0.32) 1px, transparent 1px, transparent ${colStep}%)`,
            `repeating-linear-gradient(to bottom, rgba(16,32,64,0.32), rgba(16,32,64,0.32) 1px, transparent 1px, transparent ${rowStep}%)`,
        ].join(",");
    }

    function setMapImage() {
        floorMap.src = cfg.floorImageTemplate;
    }

    function drawSelectedCell(cellX, cellY) {
        markerLayer.innerHTML = "";
        const rect = mapWrap.getBoundingClientRect();
        const cellWidth = rect.width / cfg.cols;
        const cellHeight = rect.height / cfg.rows;
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

    mapWrap.addEventListener("click", function (event) {
        const rect = mapWrap.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const cellWidth = rect.width / cfg.cols;
        const cellHeight = rect.height / cfg.rows;
        const cellX = Math.max(0, Math.min(cfg.cols - 1, Math.floor(x / cellWidth)));
        const cellY = Math.max(0, Math.min(cfg.rows - 1, Math.floor(y / cellHeight)));

        cellXInput.value = cellX;
        cellYInput.value = cellY;
        selectedCellText.textContent = `${cellX}, ${cellY}`;
        drawSelectedCell(cellX, cellY);
    });

    blockSelect.addEventListener("change", setMapImage);
    floorSelect.addEventListener("change", setMapImage);
    window.addEventListener("resize", function () {
        if (cellXInput.value !== "" && cellYInput.value !== "") {
            drawSelectedCell(Number(cellXInput.value), Number(cellYInput.value));
        }
    });

    drawGrid();
    setMapImage();
})();
