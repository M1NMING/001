<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>无人机任务规划系统 - 航线规划与飞行监控</title>
    <!-- Mapbox GL JS 核心库 (用于3D地图) -->
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.js"></script>
    <!-- 坐标转换库 (GCJ-02 / WGS-84) 使用标准算法 -->
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            user-select: none; /* 避免拖动干扰，不影响文本输入 */
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a2a32;
            height: 100vh;
            overflow: hidden;
            color: #e0e0e0;
        }
        /* 主应用布局 */
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
            backdrop-filter: blur(4px);
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
            letter-spacing: 1px;
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
        /* 主体内容区域 */
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
        /* 航线规划页面布局: 左侧控制面板 + 右侧地图 */
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
            box-shadow: 2px 0 12px rgba(0,0,0,0.2);
        }
        .map-container {
            flex: 1;
            position: relative;
        }
        #map {
            width: 100%;
            height: 100%;
        }
        /* 控制卡片样式 */
        .card {
            background: #0f1a1ecc;
            border-radius: 16px;
            padding: 16px;
            border: 1px solid #2c5a5a;
            backdrop-filter: blur(4px);
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
            transition: 0.2s;
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
            transition: 0.2s;
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
            margin-right: 8px;
        }
        .checked {
            color: #a5d6a5;
        }
        .param-row {
            display: flex;
            justify-content: space-between;
            margin-top: 8px;
        }
        /* 飞行监控页面样式 */
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
            box-shadow: 0 8px 20px rgba(0,0,0,0.3);
        }
        .heartbeat-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .heartbeat-list {
            background: #071013;
            border-radius: 16px;
            max-height: 55vh;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
        }
        .heartbeat-item {
            padding: 10px 16px;
            border-bottom: 1px solid #1e4e4a;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            font-size: 0.75rem;
        }
        .heartbeat-time {
            color: #7cb342;
            min-width: 130px;
        }
        .sim-control {
            display: flex;
            gap: 12px;
            align-items: center;
            margin-top: 12px;
        }
        .badge {
            background: #1e3a3a;
            padding: 4px 12px;
            border-radius: 40px;
            font-size: 0.7rem;
        }
        hr {
            border-color: #2c5a55;
        }
        .coord-note {
            font-size: 0.7rem;
            color: #8aa0a0;
            margin-top: 4px;
        }
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
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
                            <label>起点 A (GCJ-02示例: 32.2322, 118.749)</label>
                            <div style="display: flex; gap: 8px;">
                                <input type="text" id="aLat" placeholder="纬度" value="32.2322">
                                <input type="text" id="aLon" placeholder="经度" value="118.749">
                            </div>
                            <button id="setABtn">⭐ 设置A点</button>
                        </div>
                        <div class="input-group">
                            <label>终点 B (GCJ-02示例: 32.2343, 118.749)</label>
                            <div style="display: flex; gap: 8px;">
                                <input type="text" id="bLat" placeholder="纬度" value="32.2343">
                                <input type="text" id="bLon" placeholder="经度" value="118.749">
                            </div>
                            <button id="setBBtn">🎯 设置B点</button>
                        </div>
                        <div class="param-row">
                            <span>🟢 A点已设</span>
                            <span id="aStatus" class="status-badge" style="background:#3a6b3a;">❌ 未设</span>
                        </div>
                        <div class="param-row">
                            <span>🔴 B点已设</span>
                            <span id="bStatus" class="status-badge" style="background:#3a6b3a;">❌ 未设</span>
                        </div>
                    </div>
                    <div class="card">
                        <h3>🚁 飞行参数</h3>
                        <div class="input-group">
                            <label>设定飞行高度 (米)</label>
                            <input type="number" id="flightAltitude" value="50" step="5">
                        </div>
                        <div class="coord-note">* 心跳包将使用此高度模拟</div>
                    </div>
                    <div class="card">
                        <h3>⚠️ 障碍物展示</h3>
                        <div class="coord-note">• 航线AB之间预设多个障碍物(红色半透明区域)<br>• 支持后期放大地图圈选</div>
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
                    <div style="background:#0a1217; border-radius: 16px; padding: 12px;">
                        <div style="display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 12px;">
                            <div>📡 最新心跳: <span id="latestTime">--:--:--</span></div>
                            <div>📍 坐标(GCJ-02): <span id="latestLatLon">--, --</span></div>
                            <div>📏 高度: <span id="latestAlt">--</span> m</div>
                            <div>🔋 电量: <span id="latestBattery">--</span>%</div>
                        </div>
                    </div>
                    <div class="heartbeat-list" id="heartbeatLog">
                        <div style="padding: 20px; text-align: center; color: #7f8c8d;">等待心跳数据...</div>
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
    // ---------- 1. 坐标转换核心 (GCJ-02 <-> WGS-84) 精确算法 ----------
    const PI = Math.PI;
    const a = 6378245.0;
    const ee = 0.00669342162296594323;
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
    function gcj02_to_wgs84(lng, lat) {
        if (outOfChina(lng, lat)) return [lng, lat];
        let dlat = transformLat(lng - 105.0, lat - 35.0);
        let dlng = transformLon(lng - 105.0, lat - 35.0);
        let radlat = lat / 180.0 * PI;
        let magic = Math.sin(radlat);
        magic = 1 - ee * magic * magic;
        let sqrtmagic = Math.sqrt(magic);
        dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * PI);
        dlng = (dlng * 180.0) / (a / sqrtmagic * Math.cos(radlat) * PI);
        let mglat = lat + dlat;
        let mglng = lng + dlng;
        return [lng * 2 - mglng, lat * 2 - mglat];
    }
    function wgs84_to_gcj02(lng, lat) {
        if (outOfChina(lng, lat)) return [lng, lat];
        let dlat = transformLat(lng - 105.0, lat - 35.0);
        let dlng = transformLon(lng - 105.0, lat - 35.0);
        let radlat = lat / 180.0 * PI;
        let magic = Math.sin(radlat);
        magic = 1 - ee * magic * magic;
        let sqrtmagic = Math.sqrt(magic);
        dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * PI);
        dlng = (dlng * 180.0) / (a / sqrtmagic * Math.cos(radlat) * PI);
        return [lng + dlng, lat + dlat];
    }
    function outOfChina(lng, lat) { return (lng < 72.004 || lng > 137.8347) || (lat < 0.8293 || lat > 55.8271); }

    // ---------- 2. Mapbox 初始化 (需 token, 请替换为有效 token，或使用公共示例，推荐注册获取) ----------
    mapboxgl.accessToken = 'pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4M29iazA2Z2gycXA4N2pmbDZmangifQ.-g_vE53SD2WrJ6t-r7mQPQ'; // 公开演示token，可能有速率限制，建议用户换成自己的
    let map;
    let currentAMarker = null, currentBMarker = null;
    let routeLayerId = 'route-line';
    let aPointWGS = null, bPointWGS = null;   // 存储WGS-84坐标用于地图显示和模拟飞行
    // 障碍物 GeoJSON (预设AB连线附近，南信大/校园区域障碍物)
    const obstaclesGeoJSON = {
        type: "FeatureCollection",
        features: [
            { type: "Feature", properties: { name: "教学楼障碍" }, geometry: { type: "Polygon", coordinates: [[[118.7482, 32.2327], [118.7488, 32.2327], [118.7488, 32.2333], [118.7482, 32.2333], [118.7482, 32.2327]]] } },
            { type: "Feature", properties: { name: "图书馆障碍" }, geometry: { type: "Polygon", coordinates: [[[118.7495, 32.2329], [118.7500, 32.2329], [118.7500, 32.2335], [118.7495, 32.2335], [118.7495, 32.2329]]] } },
            { type: "Feature", properties: { name: "体育场障碍" }, geometry: { type: "Polygon", coordinates: [[[118.7485, 32.2336], [118.7492, 32.2336], [118.7492, 32.2340], [118.7485, 32.2340], [118.7485, 32.2336]]] } },
            { type: "Feature", properties: { name: "树林障碍区" }, geometry: { type: "Polygon", coordinates: [[[118.7498, 32.2338], [118.7503, 32.2338], [118.7503, 32.2343], [118.7498, 32.2343], [118.7498, 32.2338]]] } }
        ]
    };
    
    function initMap() {
        map = new mapboxgl.Map({
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12', // 卫星+路网，便于识别障碍物
            center: [118.749, 32.2332],
            zoom: 16.5,
            pitch: 55,          // 3D俯仰角
            bearing: 0,
            antialias: true
        });
        map.on('load', () => {
            // 添加障碍物图层（半透明红色）
            map.addSource('obstacles', { type: 'geojson', data: obstaclesGeoJSON });
            map.addLayer({
                id: 'obstacles-fill',
                type: 'fill',
                source: 'obstacles',
                paint: { 'fill-color': '#ff4d4d', 'fill-opacity': 0.5, 'fill-outline-color': '#ffaa00' }
            });
            // 添加3D地形增强效果（可选）
            map.addSource('mapbox-dem', { type: 'raster-dem', url: 'mapbox://mapbox.mapbox-terrain-dem-v1', tileSize: 512, maxzoom: 14 });
            map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.2 });
            // 添加建筑物3D效果
            map.addLayer({ id: '3d-buildings', type: 'fill-extrusion', source: 'composite', 'source-layer': 'building', paint: { 'fill-extrusion-color': '#aaa', 'fill-extrusion-height': ['get', 'height'], 'fill-extrusion-base': ['get', 'min_height'], 'fill-extrusion-opacity': 0.6 } });
        });
        // 保证resize
        window.addEventListener('resize', () => map.resize());
    }

    // 更新航线图层
    function updateRouteOnMap() {
        if (!map.getSource('route')) {
            map.addSource('route', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
            map.addLayer({ id: routeLayerId, type: 'line', source: 'route', paint: { 'line-color': '#4caf50', 'line-width': 4, 'line-dasharray': [2, 1] } });
        }
        if (aPointWGS && bPointWGS) {
            const coords = [[aPointWGS.lng, aPointWGS.lat], [bPointWGS.lng, bPointWGS.lat]];
            map.getSource('route').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: coords } });
            // 计算距离简单
            const distance = getDistance(aPointWGS.lat, aPointWGS.lng, bPointWGS.lat, bPointWGS.lng);
            document.getElementById('routeDistance') && (document.getElementById('routeDistance').innerText = distance.toFixed(1));
        } else {
            if(map.getSource('route')) map.getSource('route').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [] } });
        }
    }

    function getDistance(lat1, lon1, lat2, lon2) { const R = 6371000; const φ1 = lat1 * PI/180; const φ2 = lat2 * PI/180; const Δφ = (lat2-lat1)*PI/180; const Δλ = (lon2-lon1)*PI/180; const a2 = Math.sin(Δφ/2)*Math.sin(Δφ/2) + Math.cos(φ1)*Math.cos(φ2)*Math.sin(Δλ/2)*Math.sin(Δλ/2); const c2 = 2 * Math.atan2(Math.sqrt(a2), Math.sqrt(1-a2)); return R * c2; }

    function addMarker(lngLatWGS, color, label) {
        const el = document.createElement('div'); el.className = 'marker'; el.innerHTML = `<div style="background:${color}; width:20px; height:20px; border-radius:50%; border:2px solid white; text-align:center; line-height:20px; font-weight:bold; font-size:12px;">${label}</div>`;
        return new mapboxgl.Marker(el).setLngLat([lngLatWGS.lng, lngLatWGS.lat]).addTo(map);
    }

    function updateMarkersAndRoute() {
        if (currentAMarker) currentAMarker.remove();
        if (currentBMarker) currentBMarker.remove();
        if (aPointWGS) currentAMarker = addMarker({ lng: aPointWGS.lng, lat: aPointWGS.lat }, '#4caf50', 'A');
        if (bPointWGS) currentBMarker = addMarker({ lng: bPointWGS.lng, lat: bPointWGS.lat }, '#ff5722', 'B');
        updateRouteOnMap();
        // 刷新状态UI
        const aSet = !!aPointWGS, bSet = !!bPointWGS;
        document.getElementById('aStatus').innerHTML = aSet ? '✅ 已设' : '❌ 未设';
        document.getElementById('bStatus').innerHTML = bSet ? '✅ 已设' : '❌ 未设';
        document.getElementById('monitorAStatus') && (document.getElementById('monitorAStatus').innerText = aSet ? '已设' : '未设');
        document.getElementById('monitorBStatus') && (document.getElementById('monitorBStatus').innerText = bSet ? '已设' : '未设');
        // 若模拟未启动且AB存在，可重置模拟位置到A点
        if (aSet && simIntervalId === null) resetSimToA();
    }

    // 根据输入坐标系转换至WGS-84
    function parseAndSetPoint(type) {
        let lat = parseFloat(document.getElementById(type + 'Lat').value);
        let lng = parseFloat(document.getElementById(type + 'Lon').value);
        if (isNaN(lat) || isNaN(lng)) return alert('请输入有效数字');
        const coordSys = document.getElementById('coordSysSelect').value;
        let wgsLng = lng, wgsLat = lat;
        if (coordSys === 'GCJ-02') {
            const [wgsLngV, wgsLatV] = gcj02_to_wgs84(lng, lat);
            wgsLng = wgsLngV; wgsLat = wgsLatV;
        }
        const point = { lng: wgsLng, lat: wgsLat };
        if (type === 'a') aPointWGS = point;
        else bPointWGS = point;
        updateMarkersAndRoute();
        // 若模拟正在运行，且重新设置了航点，重置模拟位置到新A
        if (simIntervalId !== null && aPointWGS) resetSimToA();
    }

    // ---------------- 心跳包模拟飞行 (基于AB线移动) ----------------
    let simIntervalId = null;
    let currentSimPos = null;     // { lat, lng } WGS-84
    let simProgress = 0;          // 0~1
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
        if (container) {
            container.innerHTML = heartbeatLogs.map(e => `<div class="heartbeat-item"><span class="heartbeat-time">${e.time}</span><span>📍 ${e.lat}, ${e.lng}</span><span>📏 ${e.alt}m</span><span>🔋 ${e.bat}%</span></div>`).join('');
            if(heartbeatLogs.length===0) container.innerHTML = '<div style="padding:20px;text-align:center;">等待心跳...</div>';
        }
        document.getElementById('latestTime').innerText = timeStr;
        document.getElementById('latestLatLon').innerText = `${gcjLat.toFixed(6)}, ${gcjLng.toFixed(6)}`;
        document.getElementById('latestAlt').innerText = altitude;
        document.getElementById('latestBattery').innerText = battery;
    }
    function updateSimulation() {
        if (!simActive) return;
        if (!aPointWGS || !bPointWGS) {
            // 没有AB点，不模拟移动，但可发送悬停心跳
            if(currentSimPos) addHeartbeatEntry(currentSimPos, parseInt(document.getElementById('flightAltitude').value), Math.floor(85 + Math.random()*10));
            return;
        }
        if (!currentSimPos) { resetSimToA(); return; }
        let step = 0.008; // 每次移动3%进度
        let newProgress = simProgress + step;
        if (newProgress >= 1) { newProgress = 1; simProgress = 1; simActive = false; if(simIntervalId) clearInterval(simIntervalId); simIntervalId=null; document.getElementById('toggleSimBtn').innerText='▶️ 开始模拟'; addHeartbeatEntry(bPointWGS, parseInt(document.getElementById('flightAltitude').value), 98); return; }
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
        if (simIntervalId) { clearInterval(simIntervalId); simIntervalId=null; }
        simActive = true;
        simIntervalId = setInterval(() => { updateSimulation(); }, 1800);
        document.getElementById('toggleSimBtn').innerText = '⏸️ 暂停模拟';
        // 发送一次起始心跳
        addHeartbeatEntry(currentSimPos, parseInt(document.getElementById('flightAltitude').value), 100);
    }
    function stopSim() { if(simIntervalId){ clearInterval(simIntervalId); simIntervalId=null; simActive=false; document.getElementById('toggleSimBtn').innerText='▶️ 开始模拟'; } }
    function startSim() { if(simIntervalId) return; if(!aPointWGS){ alert("请先设置A点"); return; } simActive=true; resetSimToA(); }
    function toggleSimulation() { if(simIntervalId) stopSim(); else startSim(); }

    // 页面切换及监控高度联动
    function switchPage(pageId) {
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
        document.getElementById(pageId + 'Page').classList.add('active-page');
        if(pageId === 'planning') map.resize();
        else { document.getElementById('monitorAltValue').innerText = document.getElementById('flightAltitude').value; }
        setInterval(() => { if(document.getElementById('monitorAltValue')) document.getElementById('monitorAltValue').innerText = document.getElementById('flightAltitude').value; }, 500);
    }
    // 事件绑定与初始化
    window.onload = () => {
        initMap();
        document.getElementById('setABtn').onclick = () => parseAndSetPoint('a');
        document.getElementById('setBBtn').onclick = () => parseAndSetPoint('b');
        document.getElementById('toggleSimBtn').onclick = toggleSimulation;
        document.getElementById('resetSimBtn').onclick = () => { if(aPointWGS) resetSimToA(); else alert('请先设置A点'); };
        document.querySelectorAll('.nav-btn').forEach(btn => { btn.onclick = () => { switchPage(btn.getAttribute('data-page')); document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); }; });
        document.getElementById('coordSysSelect').onchange = (e) => { document.getElementById('globalCoordSysLabel').innerText = e.target.value; };
        setInterval(() => { if(map) map.resize(); }, 300);
        // 预置默认A/B (示例GCJ-02坐标)
        setTimeout(() => { parseAndSetPoint('a'); parseAndSetPoint('b'); startSim(); }, 1000);
    };
</script>
</body>
</html>
