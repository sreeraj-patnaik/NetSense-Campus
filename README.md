# NetSense Campus

## Floor-wise Wi-Fi & Mobile Signal Heatmap using Floor-Map Pin Tagging with ML-based Signal Prediction and Dead-Zone Analytics

---

## 📌 Overview

**NetSense Campus** is a Web Application + Android scanning system designed to measure, visualize, and analyze indoor network connectivity across a campus environment.

The system generates block-wise and floor-wise heatmaps showing Wi-Fi and Mobile signal strength using indoor floor-map coordinates instead of GPS. Signal scans collected from Android devices are stored in a backend database, aggregated per grid cell, and enhanced using Machine Learning to predict missing areas and identify connectivity dead zones.

This project helps students, administrators, and IT teams understand network coverage quality and identify weak regions for infrastructure improvement.

---

## 🎯 Objectives

* Provide block-wise and floor-wise connectivity heatmaps
* Support filtering:

  * Wi-Fi by SSID
  * Mobile by Provider and Network Type (4G / 5G)
* Collect indoor scan locations using floor-map coordinates (not GPS)
* Prevent incorrect scan positions using blocked grid cells
* Store raw scans and compute aggregated signal strength
* Predict missing cell values using ML models
* Detect dead zones automatically
* Generate connectivity analytics:

  * Coverage score
  * Best zones
  * Worst zones
  * Provider comparison

---

## 🏗 System Architecture

Android App
→ Collects signal scans and pin location
→ Sends data via REST API

Django Backend
→ Stores raw scans
→ Aggregates signal values per grid cell
→ Runs ML prediction module
→ Generates heatmap data

Web Frontend
→ Displays floor map heatmap overlays
→ Provides analytics dashboards

---

## 📐 Core Concept: Floor Map Grid Model

Each floor map is divided into a grid.

* Floor image uploaded by admin
* Grid defined by rows × columns
* Each grid cell represents a physical indoor area
* Invalid or outside areas marked as blocked

### Pin-to-Cell Conversion

```
cell_x = floor(x / cellWidth)
cell_y = floor(y / cellHeight)
cell_id = cell_y * cols + cell_x
```

Blocked cells reject scans to maintain data quality.

---

## 📱 Android App Features

### Wi-Fi Scanning

Collected data:

* SSID
* BSSID
* RSSI (dBm)
* Frequency band
* Timestamp
* Block, Floor, Cell ID

### Mobile Network Scanning

Collected data:

* Provider (Jio/Airtel/Vi/BSNL)
* Network Type (4G/5G)
* Signal strength metric
* Timestamp
* Block, Floor, Cell ID

Scans are uploaded in JSON format through REST APIs.

---

## ⚙ Backend (Django + DRF)

Responsibilities:

* Store raw scan records
* Validate payloads
* Aggregate scans per cell:

  * Median signal strength
  * Scan count (confidence)
* Provide heatmap APIs
* Execute ML prediction for missing cells
* Detect dead zones

---

## 🌡 Heatmap Visualization

The web interface allows:

* Block selection
* Floor selection
* Network mode toggle (Wi-Fi / Mobile)
* Filtering:

  * Wi-Fi SSID
  * Mobile provider + network type

Heatmap colors:

* Green — Strong signal
* Yellow — Medium
* Red — Weak
* Grey — Blocked / No Data

---

## 🤖 ML & Data Science Features

### Missing Cell Prediction

Used when cells lack scan data.

Possible models:

* KNN Regression (baseline)
* Random Forest Regression (optional)
* Distance-based interpolation (optional)

Inputs:

* Cell coordinates (x, y)
* Network parameters
* Historical scan data

Outputs:

* Predicted signal strength

---

### Dead Zone Detection

Dead zones identified using:

* Threshold rule (e.g., RSSI < -85 dBm)
* Optional clustering of weak regions

Outputs:

* Dead zone list
* Weakest connectivity areas

---

### Coverage Analytics

* Floor coverage score
* Best connectivity regions
* Worst connectivity regions
* Provider comparison

---

## 🧰 Tech Stack

* Backend: Django + Django REST Framework
* Database: PostgreSQL (recommended)
* Web Frontend: HTML, CSS, JavaScript
* Android App: Kotlin / Java
* ML Module: Python (Pandas, NumPy, Scikit-learn)

---

## 📊 Data Model (Core Entities)

* Block
* Floor (with grid configuration)
* ScanRawWiFi
* ScanRawMobile
* CellAggregate
* PredictionCell

---

## 🔌 Example API Payload

### Wi-Fi Scan

```
{
  "mode": "wifi",
  "block": "A",
  "floor": 2,
  "cell_id": 18,
  "ssid": "LIET_WIFI",
  "bssid": "aa:bb:cc:dd:ee:ff",
  "rssi": -72,
  "frequency": 2412,
  "timestamp": "2026-01-29T10:22:10Z",
  "device_id": "android_abc123"
}
```

---

## 👥 Team

* Sreeraj Dabbiru — 24kd1a1513
* Harika Tarlada
* Venkatesh Vajja

---

## 🚧 Development Scope (MVP)

Included:

* Android scan collection
* Backend aggregation
* Heatmap visualization
* ML-based signal prediction
* Dead zone analytics

Excluded (Future Work):

* Real-time continuous tracking
* BLE indoor positioning
* Automatic floor map extraction

---

## 🧪 Testing Strategy

* Android:

  * Pin conversion validation
  * Blocked cell rejection
* Backend:

  * Aggregation logic
  * Heatmap API validation
* Web:

  * Map overlay accuracy
  * Filtering correctness

---

## 📄 License

Academic project for educational and research purposes.

---

## 🚀 Status

Active development — MVP phase.
