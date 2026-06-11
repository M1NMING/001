<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>无人机任务规划系统 - 航线规划与飞行监控</title>
    <!-- Mapbox GL JS 核心库 (3D地图) -->
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a2a32;
            height: 100vh;
            overflow: hidden;
            color: #e0e0e0;
        }
        .app-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        /* 顶部导航栏 */
        .nav-bar {
            background: #0f1a1f;
            padding: 0 24px;
            display: flex;
            gap: 8px;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            z-index: 10;
            border-bottom: 1px solid #2c3e3a;
        }
        .nav-btn {
            background: transparent;
            border: none;
            color: #b0bec5;
            font-size: 1.1rem;
            font-weight: 600;
            padding: 14px 24px;
            cursor: pointer;
            transition: all 0.2s ease;
            border-bottom: 3px solid transparent;
        }
        .nav-btn.active {
            color: #4caf50;
            border-bottom-color: #4caf50;
            background: rgba(76,175,80,0.1);
        }
        .nav-btn:hover:not(.active) {
            color: #cfd8dc;
            background: #1e2f38;
        }
        .pages-container {
            flex: 1;
            position: relative;
            overflow: hidden;
        }
        .page {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            transition: opacity 0.25s ease;
            opacity: 0;
            visibility: hidden;
            display: flex;
        }
        .page.active-page {
            opacity: 1;
            visibility: visible;
        }
        /* 航线规划页面布局 */
        .planning-layout {
            display: flex;
            width: 100%;
            height: 100%;
            background: #1e2c32;
        }
        .control-panel {
            width: 320px;
            background: rgba(18, 28, 32, 0.85);
            backdrop-filter: blur(12px);
            border-right: 1px solid #2c4a4a;
            padding: 20px 16px;
            overflow-y: auto;
            z-index: 2;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }
        .map-container {
            flex: 1;
            position: relative;
        }
        #map {
            width: 100%;
            height: 100%;
        }
        .card {
            background: #0f1a1ecc;
            border-radius: 16px;
            padding: 16px;
            border: 1px solid #2c5a5a;
        }
        .card h3 {
            font-size: 1rem;
            margin-bottom: 12px;
            border-left: 4px solid #4caf50;
            padding-left: 10px;
            color: #ccffcc;
        }
        .input-group {
            margin-bottom: 14px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .input-group label {
            font-size: 0.8rem;
            font-weight: 500;
            color: #bcd0d0;
        }
        input, select, button {
            background: #1e2f38;
            border: 1px solid #2e6b6b;
            padding: 8px 12px;
            border-radius: 8px;
            color: #f0f0f0;
            font-size: 0.9rem;
            outline: none;
        }
        input:focus, select:focus {
            border-color: #4caf50;
            box-shadow: 0 0 0 2px rgba(76,175,80,0.2);
        }
        button {
            background: #2c5a5a;
            cursor: pointer;
            font-weight: bold;
            margin-top: 6px;
        }
        button:hover {
            background: #3e7e7e;
            border-color: #6fbf6f;
        }
        .status-badge {
            display: inline-block;
            background: #2c3e2e;
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 0.75rem;
            font-weight: bold;
        }
        .param-row {
            display: flex;
            justify-content: space-between;
            margin-top: 8px;
        }
        /* 飞行监控页面 */
        .monitor-layout {
            width: 100%;
            height: 100%;
            background: #111d22;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }
        .heartbeat-panel {
            background: #0e181c;
            border-radius: 24px;
            border: 1px solid #2b6b5e;
            padding: 20px;
        }
        .heartbeat-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .heartbeat-list {
            background: #071013;
            border-radius: 16px;
            max-height: 55vh;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.8rem;
        }
        .heartbeat-item {
            padding: 10px 16px;
            border-bottom: 1px solid #1e4e4a;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }
        .heartbeat-time {
            color: #7cb342;
            min-width: 130px;
        }
        .sim-control {
            display: flex;
            gap: 12px;
            align-items: center;
        }
        .badge {
            background: #1e3a3a;
            padding: 4px 12px;
            border-radius: 40px;
            font-size: 0.7rem;
        }
        .coord-note {
            font-size: 0.7rem;
            color: #8aa0a0;
            margin-top: 4px;
        }
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #1a2a2a;
        }
        ::-webkit-scrollbar-thumb {
            background: #4caf50;
            border-radius: 4px;
        }
    </style>
</head>
<body>
<div class="app-container">
    <div class="nav-bar">
        <button class="nav-btn active" data-page="planning">🗺️ 航线规划</button>
        <button class="nav-btn" data-page="monitor">📡 飞行监控</button>
        <div style="flex:1"></div>
        <div style="font-size:12px; background:#1e3a3a; padding:4px 12px; border-radius:20px;">
            🧭 坐标系: <span id="globalCoordSysLabel">GCJ-02</span>
        </div>
    </div>
    <div class="pages-container">
        <!-- 航线规划页面 -->
        <div id="planningPage" class="page active-page">
            <div class="planning-layout">
                <div class="control-panel">
                    <div class="card">
                        <h3>📍 坐标系设置</h3>
                        <div class="input-group">
                            <label>输入坐标系 (影响A/B点坐标解释)</label>
                            <select id="coordSysSelect">
                                <option value="GCJ-02" selected>GCJ-02 (高德/百度)</option>
                                <option value="WGS-84">WGS-84 (GPS)</option>
                            </select>
                            <div class="coord-note">地图底图基于WGS-84，系统自动转换显示</div>
                        </div>
                    </div>
                    <div class="card">
                        <h3>✈️ 航点设置 (校园内)</h3>
                        <div class="input-group">
                            <label>起点 A (示例GCJ-02: 32.2322, 118.749)</label>
                            <div style="display: flex; gap: 8px;">
                                <input type="text" id="aLat" placeholder="纬度" value="32.2322">
                                <input type="text" id="aLon" placeholder="经度" value="118.749">
                            </div>
                            <button id="setABtn">⭐ 设置A点</button>
                        </div>
                        <div class="input-group">
                            <label>终点 B (示例GCJ-02: 32.2343, 118.749)</label>
                            <div style="display: flex; gap: 8px;">
                                <input type="text" id="bLat" placeholder="纬度" value="32.2343">
                                <input type="text" id="bLon" placeholder="经度" value="118.749">
                            </div>
                            <button id="setBBtn">🎯 设置B点</button>
                        </div>
                        <div class="param-row">
                            <span>🟢 A点已设</span>
                            <span id="aStatus" class="status-badge">❌ 未设</span>
                        </div>
                        <div class="param-row">
                            <span>🔴 B点已设</span>
                            <span id="bStatus" class="status-badge">❌ 未设</span>
                        </div>
                    </div>
                    <div class="card">
                        <h3>🚁 飞行参数</h3>
                        <div class="input-group">
                            <label>设定飞行高度 (米)</label>
                            <input type="number" id="flightAltitude" value="50" step="5">
                        </div>
                    </div>
                    <div class="card">
                        <h3>⚠️ 障碍物展示</h3>
                        <div class="coord-note">• 航线AB之间预设多个障碍物(红色半透明区域)<br>• 支持放大地图查看，辅助航线避障</div>
                    </div>
                </div>
                <div class="map-container">
                    <div id="map"></div>
                </div>
            </div>
        </div>

        <!-- 飞行监控页面 (心跳包显示) -->
        <div id="monitorPage" class="page">
            <div class="monitor-layout">
                <div class="heartbeat-panel">
                    <div class="heartbeat-header">
                        <h2>💓 实时心跳包数据流</h2>
                        <div class="sim-control">
                            <span class="badge">🔄 模拟飞行中</span>
                            <button id="toggleSimBtn">⏸️ 暂停模拟</button>
                            <button id="resetSimBtn">🔄 重置至A点</button>
                        </div>
                    </div>
                    <div style="background:#0a1217; border-radius: 16px; padding: 12px; margin-bottom: 16px;">
                        <div style="display: flex; gap: 24px; flex-wrap: wrap;">
                            <div>📡 最新心跳: <span id="latestTime">--:--:--</span></div>
                            <div>📍 坐标(GCJ-02): <span id="latestLatLon">--, --</span></div>
                            <div>📏 高度: <span id="latestAlt">--</span> m</div>
                            <div>🔋 电量: <span id="latestBattery">--</span>%</div>
                        </div>
                    </div>
                    <div class="heartbeat-list" id="heartbeatLog">
                        <div style="padding: 20px; text-align: center;">等待心跳数据...</div>
                    </div>
                </div>
                <div class="card" style="background:#0e181c;">
                    <h3>📋 系统状态 & 飞行参数</h3>
                    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                        <div>✅ A点已设: <span id="monitorAStatus">否</span></div>
                        <div>✅ B点已设: <span id="monitorBStatus">否</span></div>
                        <div>🛫 巡航高度: <span id="monitorAltValue">50</span> m</div>
                        <div>📐 航线长度: <span id="routeDistance">--</span> m</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    // ==================== 坐标转换核心 (GCJ-02 <-> WGS-84) ====================
    const PI = Math.PI;
    const A = 6378245.0;
    const EE = 0.00669342162296594323;

    function transformLat(x, y) {
        let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0;
        ret += (160.0 * Math.sin(y / 12.0 * PI) + 320 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0;
        return ret;
    }
    function transformLon(x, y) {
        let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * PI)) * 2.0 / 3.0;
        ret += (150.0 * Math.sin(x / 12.0 * PI) + 300.0 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0;
        return ret;
    }
    function outOfChina(lng, lat) {
        return (lng < 72.004 || lng > 137.8347) || (lat < 0.8293 || lat > 55.8271);
    }
    function gcj02_to_wgs84(lng, lat) {
        if (outOfChina(lng, lat)) return [lng, lat];
        let dlat = transformLat(lng - 105.0, lat - 35.0);
        let dlng = transformLon(lng - 105.0, lat - 35.0);
        let radlat = lat / 180.0 * PI;
        let magic = Math.sin(radlat);
        magic = 1 - EE * magic * magic;
        let sqrtmagic = Math.sqrt(magic);
        dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI);
        dlng = (dlng * 180.0) / (A / sqrtmagic * Math.cos(radlat) * PI);
        return [lng * 2 - (lng + dlng), lat * 2 - (lat + dlat)];
    }
    function wgs84_to_gcj02(lng, lat) {
        if (outOfChina(lng, lat)) return [lng, lat];
        let dlat = transformLat(lng - 105.0, lat - 35.0);
        let dlng = transformLon(lng - 105.0, lat - 35.0);
        let radlat = lat / 180.0 * PI;
        let magic = Math.sin(radlat);
        magic = 1 - EE * magic * magic;
        let sqrtmagic = Math.sqrt(magic);
        dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI);
        dlng = (dlng * 180.0) / (A / sqrtmagic * Math.cos(radlat) * PI);
        return [lng + dlng, lat + dlat];
    }

    // ==================== Mapbox 初始化 ====================
    mapboxgl.accessToken = 'pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4M29iazA2Z2gycXA4N2pmbDZmangifQ.-g_vE53SD2WrJ6t-r7mQPQ';
    let map;
    let currentAMarker = null, currentBMarker = null;
    let aPointWGS = null, bPointWGS = null;

    // 障碍物 (校园内AB线附近的几个多边形)
    const obstaclesGeoJSON = {
        type: "FeatureCollection",
        features: [
            { type: "Feature", properties: { name: "教学楼" }, geometry: { type: "Polygon", coordinates: [[[118.7482, 32.2327], [118.7488, 32.2327], [118.7488, 32.2333], [118.7482, 32.2333], [118.7482, 32.2327]]] } },
            { type: "Feature", properties: { name: "图书馆" }, geometry: { type: "Polygon", coordinates: [[[118.7495, 32.2329], [118.7500, 32.2329], [118.7500, 32.2335], [118.7495, 32.2335], [118.7495, 32.2329]]] } },
            { type: "Feature", properties: { name: "体育场" }, geometry: { type: "Polygon", coordinates: [[[118.7485, 32.2336], [118.7492, 32.2336], [118.7492, 32.2340], [118.7485, 32.2340], [118.7485, 32.2336]]] } },
            { type: "Feature", properties: { name: "树林区" }, geometry: { type: "Polygon", coordinates: [[[118.7498, 32.2338], [118.7503, 32.2338], [118.7503, 32.2343], [118.7498, 32.2343], [118.7498, 32.2338]]] } }
        ]
    };

    function initMap() {
        map = new mapboxgl.Map({
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [118.749, 32.2332],
            zoom: 16.5,
            pitch: 55,
            bearing: 0,
            antialias: true
        });
        map.on('load', () => {
            map.addSource('obstacles', { type: 'geojson', data: obstaclesGeoJSON });
            map.addLayer({
                id: 'obstacles-fill',
                type: 'fill',
                source: 'obstacles',
                paint: { 'fill-color': '#ff4d4d', 'fill-opacity': 0.5, 'fill-outline-color': '#ffaa00' }
            });
            // 简易3D地形
            map.addSource('mapbox-dem', {
                type: 'raster-dem',
                url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
                tileSize: 512,
                maxzoom: 14
            });
            map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.2 });
        });
    }

    function addMarker(lngLatWGS, color, label) {
        const el = document.createElement('div');
        el.innerHTML = `<div style="background:${color}; width:20px; height:20px; border-radius:50%; border:2px solid white; text-align:center; line-height:20px; font-weight:bold; font-size:12px;">${label}</div>`;
        return new mapboxgl.Marker(el).setLngLat([lngLatWGS.lng, lngLatWGS.lat]).addTo(map);
    }

    function updateRouteOnMap() {
        if (!map.getSource('route')) {
            map.addSource('route', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
            map.addLayer({ id: 'route-line', type: 'line', source: 'route', paint: { 'line-color': '#4caf50', 'line-width': 4, 'line-dasharray': [2, 1] } });
        }
        if (aPointWGS && bPointWGS) {
            const coords = [[aPointWGS.lng, aPointWGS.lat], [bPointWGS.lng, bPointWGS.lat]];
            map.getSource('route').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: coords } });
            const dist = getDistance(aPointWGS.lat, aPointWGS.lng, bPointWGS.lat, bPointWGS.lng);
            document.getElementById('routeDistance').innerText = dist.toFixed(1);
        } else {
            if (map.getSource('route')) map.getSource('route').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [] } });
        }
    }

    function getDistance(lat1, lon1, lat2, lon2) {
        const R = 6371000;
        const φ1 = lat1 * PI / 180;
        const φ2 = lat2 * PI / 180;
        const Δφ = (lat2 - lat1) * PI / 180;
        const Δλ = (lon2 - lon1) * PI / 180;
        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    function updateMarkersAndRoute() {
        if (currentAMarker) currentAMarker.remove();
        if (currentBMarker) currentBMarker.remove();
        if (aPointWGS) currentAMarker = addMarker({ lng: aPointWGS.lng, lat: aPointWGS.lat }, '#4caf50', 'A');
        if (bPointWGS) currentBMarker = addMarker({ lng: bPointWGS.lng, lat: bPointWGS.lat }, '#ff5722', 'B');
        updateRouteOnMap();
        const aSet = !!aPointWGS, bSet = !!bPointWGS;
        document.getElementById('aStatus').innerHTML = aSet ? '✅ 已设' : '❌ 未设';
        document.getElementById('bStatus').innerHTML = bSet ? '✅ 已设' : '❌ 未设';
        document.getElementById('monitorAStatus').innerText = aSet ? '已设' : '未设';
        document.getElementById('monitorBStatus').innerText = bSet ? '已设' : '未设';
    }

    function parseAndSetPoint(type) {
        let lat = parseFloat(document.getElementById(type + 'Lat').value);
        let lng = parseFloat(document.getElementById(type + 'Lon').value);
        if (isNaN(lat) || isNaN(lng)) return alert('请输入有效数字');
        const coordSys = document.getElementById('coordSysSelect').value;
        let wgsLng = lng, wgsLat = lat;
        if (coordSys === 'GCJ-02') {
            const [wLng, wLat] = gcj02_to_wgs84(lng, lat);
            wgsLng = wLng; wgsLat = wLat;
        }
        const point = { lng: wgsLng, lat: wgsLat };
        if (type === 'a') aPointWGS = point;
        else bPointWGS = point;
        updateMarkersAndRoute();
        if (simIntervalId !== null && aPointWGS) resetSimToA();
    }

    // ==================== 心跳包模拟 ====================
    let simIntervalId = null;
    let currentSimPos = null;
    let simProgress = 0;
    let simActive = true;
    const heartbeatLogs = [];

    function addHeartbeatEntry(posWGS, altitude, battery) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        const [gcjLng, gcjLat] = wgs84_to_gcj02(posWGS.lng, posWGS.lat);
        const entry = { time: timeStr, lat: gcjLat.toFixed(6), lng: gcjLng.toFixed(6), alt: altitude, bat: battery };
        heartbeatLogs.unshift(entry);
        if (heartbeatLogs.length > 30) heartbeatLogs.pop();
        const container = document.getElementById('heartbeatLog');
        container.innerHTML = heartbeatLogs.map(e => `<div class="heartbeat-item"><span class="heartbeat-time">${e.time}</span><span>📍 ${e.lat}, ${e.lng}</span><span>📏 ${e.alt}m</span><span>🔋 ${e.bat}%</span></div>`).join('');
        document.getElementById('latestTime').innerText = timeStr;
        document.getElementById('latestLatLon').innerText = `${gcjLat.toFixed(6)}, ${gcjLng.toFixed(6)}`;
        document.getElementById('latestAlt').innerText = altitude;
        document.getElementById('latestBattery').innerText = battery;
    }

    function updateSimulation() {
        if (!simActive) return;
        if (!aPointWGS || !bPointWGS) {
            if(currentSimPos) addHeartbeatEntry(currentSimPos, parseInt(document.getElementById('flightAltitude').value), 85);
            return;
        }
        if (!currentSimPos) { resetSimToA(); return; }
        let step = 0.008;
        let newProgress = simProgress + step;
        if (newProgress >= 1) {
            newProgress = 1; simProgress = 1; simActive = false;
            if(simIntervalId) clearInterval(simIntervalId);
            simIntervalId = null;
            document.getElementById('toggleSimBtn').innerText = '▶️ 开始模拟';
            addHeartbeatEntry(bPointWGS, parseInt(document.getElementById('flightAltitude').value), 98);
            return;
        }
        simProgress = newProgress;
        const lat = aPointWGS.lat + (bPointWGS.lat - aPointWGS.lat) * simProgress;
        const lng = aPointWGS.lng + (bPointWGS.lng - aPointWGS.lng) * simProgress;
        currentSimPos = { lat, lng };
        const altitude = parseInt(document.getElementById('flightAltitude').value);
        const battery = Math.max(60, 99 - Math.floor(simProgress * 35));
        addHeartbeatEntry(currentSimPos, altitude, battery);
    }

    function resetSimToA() {
        if (!aPointWGS) return;
        simProgress = 0;
        currentSimPos = { lat: aPointWGS.lat, lng: aPointWGS.lng };
        if (simIntervalId) { clearInterval(simIntervalId); simIntervalId = null; }
        simActive = true;
        simIntervalId = setInterval(() => { updateSimulation(); }, 1800);
        document.getElementById('toggleSimBtn').innerText = '⏸️ 暂停模拟';
        addHeartbeatEntry(currentSimPos, parseInt(document.getElementById('flightAltitude').value), 100);
    }

    function stopSim() {
        if(simIntervalId){ clearInterval(simIntervalId); simIntervalId = null; simActive = false; document.getElementById('toggleSimBtn').innerText = '▶️ 开始模拟'; }
    }
    function startSim() {
        if(simIntervalId) return;
        if(!aPointWGS){ alert("请先设置A点"); return; }
        simActive = true;
        resetSimToA();
    }
    function toggleSimulation() {
        if(simIntervalId) stopSim();
        else startSim();
    }

    function switchPage(pageId) {
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
        document.getElementById(pageId + 'Page').classList.add('active-page');
        if(pageId === 'planning') map.resize();
    }

    // 监听高度变化同步到监控页
    setInterval(() => {
        const alt = document.getElementById('flightAltitude').value;
        document.getElementById('monitorAltValue').innerText = alt;
    }, 500);

    window.onload = () => {
        initMap();
        document.getElementById('setABtn').onclick = () => parseAndSetPoint('a');
        document.getElementById('setBBtn').onclick = () => parseAndSetPoint('b');
        document.getElementById('toggleSimBtn').onclick = toggleSimulation;
        document.getElementById('resetSimBtn').onclick = () => { if(aPointWGS) resetSimToA(); else alert('请先设置A点'); };
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.onclick = () => {
                switchPage(btn.getAttribute('data-page'));
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            };
        });
        document.getElementById('coordSysSelect').onchange = (e) => {
            document.getElementById('globalCoordSysLabel').innerText = e.target.value;
        };
        setTimeout(() => {
            parseAndSetPoint('a');
            parseAndSetPoint('b');
            startSim();
        }, 1000);
    };
</script>
</body>
</html>
