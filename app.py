<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>无人机地面站系统 - 航线规划与飞行监控</title>
    <!-- Mapbox GL JS 样式与库 (支持3D地形) -->
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.5.1/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v3.5.1/mapbox-gl.js"></script>
    <!-- 字体图标库 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <!-- 日期处理辅助 -->
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #1a202c;
            color: #e2e8f0;
            height: 100vh;
            overflow: hidden;
        }

        /* 整体布局 */
        .app-container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        /* 顶部导航栏 */
        .navbar {
            background-color: #0f172a;
            padding: 0.8rem 2rem;
            display: flex;
            gap: 1.5rem;
            border-bottom: 1px solid #334155;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            z-index: 20;
        }

        .nav-btn {
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 1.1rem;
            font-weight: 600;
            padding: 0.5rem 1.2rem;
            border-radius: 30px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-btn i {
            font-size: 1.1rem;
        }

        .nav-btn:hover {
            background-color: #1e293b;
            color: #cbd5e1;
        }

        .nav-btn.active {
            background-color: #3b82f6;
            color: white;
            box-shadow: 0 2px 6px rgba(59,130,246,0.4);
        }

        /* 主内容区域，页面切换 */
        .page {
            flex: 1;
            display: none;
            overflow-y: auto;
            position: relative;
        }

        .page.active-page {
            display: flex;
            flex-direction: column;
        }

        /* 航线规划页面布局 (地图+侧边栏) */
        .map-layout {
            display: flex;
            flex: 1;
            overflow: hidden;
        }

        .sidebar {
            width: 320px;
            background: rgba(15, 25, 45, 0.95);
            backdrop-filter: blur(10px);
            border-right: 1px solid #334155;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 1.2rem;
            overflow-y: auto;
            z-index: 10;
        }

        .map-container {
            flex: 1;
            position: relative;
        }

        #map {
            height: 100%;
            width: 100%;
        }

        /* 控制卡片样式 */
        .control-card {
            background: #0f172a;
            border-radius: 16px;
            padding: 1rem;
            border: 1px solid #334155;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }

        .control-card h3 {
            font-size: 1.1rem;
            margin-bottom: 0.8rem;
            color: #f1f5f9;
            border-left: 4px solid #3b82f6;
            padding-left: 0.6rem;
        }

        .input-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 12px;
        }

        .input-group label {
            font-size: 0.8rem;
            color: #94a3b8;
        }

        .coord-row {
            display: flex;
            gap: 8px;
        }

        .coord-row input {
            flex: 1;
            background: #1e293b;
            border: 1px solid #475569;
            color: #f1f5f9;
            padding: 6px 10px;
            border-radius: 8px;
            font-size: 0.85rem;
        }

        select, button {
            background: #1e293b;
            border: 1px solid #475569;
            color: #e2e8f0;
            padding: 6px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }

        button {
            background: #3b82f6;
            border-color: #3b82f6;
            font-weight: 500;
        }

        button:hover {
            background: #2563eb;
        }

        .btn-outline {
            background: transparent;
            border: 1px solid #3b82f6;
            color: #3b82f6;
        }

        .btn-outline:hover {
            background: #3b82f6;
            color: white;
        }

        .obstacle-item {
            background: #1e293b;
            border-radius: 12px;
            padding: 8px 12px;
            margin-top: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
        }

        .obstacle-badge {
            background: #ef4444;
            width: 10px;
            height: 10px;
            border-radius: 10px;
            display: inline-block;
            margin-right: 8px;
        }

        /* 飞行监控页面布局 */
        .monitor-layout {
            display: flex;
            flex-direction: column;
            padding: 20px;
            gap: 20px;
            height: 100%;
        }

        .heartbeat-panel {
            background: #0f172a;
            border-radius: 20px;
            border: 1px solid #334155;
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .heartbeat-header {
            padding: 1rem;
            border-bottom: 1px solid #334155;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .heartbeat-list {
            flex: 1;
            overflow-y: auto;
            padding: 0.5rem;
            font-family: monospace;
        }

        .heartbeat-item {
            background: #1e293b;
            margin: 8px 0;
            padding: 10px;
            border-radius: 12px;
            font-size: 0.8rem;
            border-left: 3px solid #10b981;
        }

        .sim-controls {
            background: #0f172a;
            border-radius: 16px;
            padding: 1rem;
            display: flex;
            gap: 12px;
            align-items: center;
        }

        /* 功能页面简单展示 */
        .functions-panel {
            padding: 2rem;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100%;
        }

        .info-card {
            background: #0f172a;
            border-radius: 28px;
            padding: 2rem;
            max-width: 500px;
            text-align: center;
        }

        /* 滚动条 */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #1e293b;
        }
        ::-webkit-scrollbar-thumb {
            background: #3b82f6;
            border-radius: 4px;
        }
    </style>
</head>
<body>
<div class="app-container">
    <div class="navbar">
        <button class="nav-btn" data-page="functions"><i class="fas fa-tachometer-alt"></i> 功能页面</button>
        <button class="nav-btn active" data-page="route-planning"><i class="fas fa-draw-polygon"></i> 航线规划</button>
        <button class="nav-btn" data-page="flight-monitor"><i class="fas fa-heartbeat"></i> 飞行监控</button>
    </div>

    <!-- 功能页面 -->
    <div id="functions-page" class="page">
        <div class="functions-panel">
            <div class="info-card">
                <i class="fas fa-robot" style="font-size: 48px; color: #3b82f6;"></i>
                <h2 style="margin: 16px 0;">智能无人机地面站</h2>
                <p>✅ 支持坐标系转换 (WGS-84 ↔ GCJ-02)</p>
                <p>✅ 3D地图 / 障碍物管理 / 航线规划</p>
                <p>✅ 实时心跳包监控 (模拟接收)</p>
                <p>✅ 支持校园内多点障碍物圈选添加</p>
                <p style="margin-top: 20px; font-size: 0.8rem; color:#94a3b8;">南京某校园区域 | 高精度地形模拟</p>
            </div>
        </div>
    </div>

    <!-- 航线规划页面 (地图 + 控制栏) -->
    <div id="route-planning-page" class="page active-page">
        <div class="map-layout">
            <div class="sidebar">
                <div class="control-card">
                    <h3><i class="fas fa-map-marker-alt"></i> 起点 A (GCJ-02)</h3>
                    <div class="input-group">
                        <label>坐标系类型</label>
                        <select id="startCoordType">
                            <option value="GCJ-02" selected>GCJ-02 (高德/百度)</option>
                            <option value="WGS-84">WGS-84</option>
                        </select>
                    </div>
                    <div class="coord-row">
                        <input type="text" id="startLat" placeholder="纬度" value="32.2322">
                        <input type="text" id="startLng" placeholder="经度" value="118.749">
                    </div>
                    <button id="setStartBtn"><i class="fas fa-location-dot"></i> 设置A点</button>
                </div>

                <div class="control-card">
                    <h3><i class="fas fa-map-pin"></i> 终点 B (GCJ-02)</h3>
                    <div class="input-group">
                        <label>坐标系类型</label>
                        <select id="endCoordType">
                            <option value="GCJ-02" selected>GCJ-02 (高德/百度)</option>
                            <option value="WGS-84">WGS-84</option>
                        </select>
                    </div>
                    <div class="coord-row">
                        <input type="text" id="endLat" placeholder="纬度" value="32.2343">
                        <input type="text" id="endLng" placeholder="经度" value="118.749">
                    </div>
                    <button id="setEndBtn"><i class="fas fa-location-dot"></i> 设置B点</button>
                </div>

                <div class="control-card">
                    <h3><i class="fas fa-plane"></i> 飞行参数</h3>
                    <div class="input-group">
                        <label>设定飞行高度 (米)</label>
                        <input type="number" id="flightAltitude" value="50" step="5">
                    </div>
                    <div class="input-group">
                        <label>障碍物管理 (点击地图圆形圈选)</label>
                        <button id="toggleAddObstacleMode" class="btn-outline"><i class="fas fa-plus-circle"></i> 添加障碍物模式</button>
                        <button id="clearAllObstacles" class="btn-outline" style="margin-top: 6px;"><i class="fas fa-trash-alt"></i> 清空障碍物</button>
                    </div>
                    <div id="obstacleList" style="max-height: 180px; overflow-y: auto; margin-top: 10px;">
                        <!-- 动态显示障碍物列表 -->
                    </div>
                </div>
                <div class="control-card">
                    <p style="font-size: 0.7rem; color:#94a3b8;"><i class="fas fa-info-circle"></i> 注：A/B点需位于校园内，中间预置+可添加障碍物。地图3D地形开启，支持坐标自动转换</p>
                </div>
            </div>
            <div class="map-container">
                <div id="map"></div>
            </div>
        </div>
    </div>

    <!-- 飞行监控页面(心跳包显示) -->
    <div id="flight-monitor-page" class="page">
        <div class="monitor-layout">
            <div class="heartbeat-panel">
                <div class="heartbeat-header">
                    <h3><i class="fas fa-heartbeat" style="color: #ef4444;"></i> 实时心跳包接收</h3>
                    <div>
                        <button id="startHeartbeatSim" class="btn-outline" style="background:#10b981;"><i class="fas fa-play"></i> 开始模拟</button>
                        <button id="stopHeartbeatSim" class="btn-outline"><i class="fas fa-stop"></i> 停止</button>
                        <button id="clearHeartbeat" class="btn-outline"><i class="fas fa-eraser"></i> 清空</button>
                    </div>
                </div>
                <div id="heartbeatLog" class="heartbeat-list">
                    <div style="text-align:center; padding:20px; color:#94a3b8;">等待心跳数据...</div>
                </div>
            </div>
            <div class="sim-controls">
                <i class="fas fa-satellite-dish"></i> 模拟无人机心跳包 (每秒接收) - 坐标基于GCJ02校园区域
                <span style="margin-left:auto; font-size:12px;"><i class="fas fa-chart-line"></i> 状态: <span id="heartbeatStatus">未启动</span></span>
            </div>
        </div>
    </div>
</div>

<script>
    // ---------------------------- 坐标系转换核心算法 (GCJ-02 <-> WGS-84) ---------------------------------
    const pi = 3.14159265358979323846;
    const a = 6378245.0;
    const ee = 0.00669342162296594323;

    function transformLat(x, y) {
        let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * pi) + 20.0 * Math.sin(2.0 * x * pi)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(y * pi) + 40.0 * Math.sin(y / 3.0 * pi)) * 2.0 / 3.0;
        ret += (160.0 * Math.sin(y / 12.0 * pi) + 320 * Math.sin(y * pi / 30.0)) * 2.0 / 3.0;
        return ret;
    }

    function transformLon(x, y) {
        let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * pi) + 20.0 * Math.sin(2.0 * x * pi)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(x * pi) + 40.0 * Math.sin(x / 3.0 * pi)) * 2.0 / 3.0;
        ret += (150.0 * Math.sin(x / 12.0 * pi) + 300.0 * Math.sin(x / 30.0 * pi)) * 2.0 / 3.0;
        return ret;
    }

    function outOfChina(lat, lon) {
        if (lon < 72.004 || lon > 137.8347) return true;
        if (lat < 0.8293 || lat > 55.8271) return true;
        return false;
    }

    // GCJ-02 转 WGS-84
    function gcj02ToWgs84(lat, lon) {
        if (outOfChina(lat, lon)) return [lat, lon];
        let dLat = transformLat(lon - 105.0, lat - 35.0);
        let dLon = transformLon(lon - 105.0, lat - 35.0);
        let radLat = lat / 180.0 * pi;
        let magic = Math.sin(radLat);
        magic = 1 - ee * magic * magic;
        let sqrtMagic = Math.sqrt(magic);
        dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * pi);
        dLon = (dLon * 180.0) / (a / sqrtMagic * Math.cos(radLat) * pi);
        let mgLat = lat + dLat;
        let mgLon = lon + dLon;
        return [lat * 2 - mgLat, lon * 2 - mgLon];
    }

    // WGS-84 转 GCJ-02 (简单辅助)
    function wgs84ToGcj02(lat, lon) {
        if (outOfChina(lat, lon)) return [lat, lon];
        let dLat = transformLat(lon - 105.0, lat - 35.0);
        let dLon = transformLon(lon - 105.0, lat - 35.0);
        let radLat = lat / 180.0 * pi;
        let magic = Math.sin(radLat);
        magic = 1 - ee * magic * magic;
        let sqrtMagic = Math.sqrt(magic);
        dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * pi);
        dLon = (dLon * 180.0) / (a / sqrtMagic * Math.cos(radLat) * pi);
        return [lat + dLat, lon + dLon];
    }

    // 统一转换用户输入 (根据坐标系选择) 到地图内部使用的WGS84
    function convertInputToWGS84(lat, lng, coordType) {
        let latNum = parseFloat(lat), lngNum = parseFloat(lng);
        if (isNaN(latNum) || isNaN(lngNum)) return null;
        if (coordType === 'GCJ-02') {
            return gcj02ToWgs84(latNum, lngNum);
        } else {
            return [latNum, lngNum];
        }
    }

    // ---------------------------- 地图初始化 & 全局变量 ---------------------------------
    mapboxgl.accessToken = 'pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4M29iazA2Z2gycXA4N2pmbDZmangifQ.-g_vE53SD2WrJ6t-r7mQPQ';  // 公开demo token, 生产环境请替换自己的key, 但足够演示
    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/satellite-streets-v12', // 卫星+路网, 显示障碍物清晰
        center: [118.749, 32.2332],
        zoom: 16.5,
        pitch: 58,
        bearing: -15,
        antialias: true
    });

    // 添加3D地形
    map.on('load', () => {
        map.addSource('mapbox-dem', {
            'type': 'raster-dem',
            'url': 'mapbox://mapbox.mapbox-terrain-dem-v1',
            'tileSize': 512,
            'maxzoom': 14
        });
        map.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 1.5 });
        // 添加3D建筑物标注效果(可有可无)
        map.addLayer({
            'id': 'sky',
            'type': 'sky',
            'paint': {
                'sky-type': 'atmosphere',
                'sky-atmosphere-sun': [0.0, 0.0],
                'sky-atmosphere-sun-intensity': 10
            }
        });
    });

    // 数据存储
    let waypoints = { start: null, end: null }; // 存储WGS84坐标
    let obstacles = []; // 每个障碍物 { lng, lat, radiusMeters, id }
    let obstacleMode = false; // 圈选添加模式
    let heartbeatInterval = null;
    
    // 预置校园内AB之间的障碍物 (3个障碍物)
    const defaultObstacles = [
        { lng: 118.7485, lat: 32.2330, radiusMeters: 28, name: "行政楼" },
        { lng: 118.7492, lat: 32.2328, radiusMeters: 22, name: "花坛障碍" },
        { lng: 118.7489, lat: 32.2337, radiusMeters: 35, name: "体育馆" }
    ];
    
    // 添加预置障碍物(转换wgs84)
    defaultObstacles.forEach(obs => {
        // 提供的坐标是GCJ02, 转换为wgs84显示在地图上
        let [wgsLat, wgsLng] = gcj02ToWgs84(obs.lat, obs.lng);
        obstacles.push({ id: Date.now() + Math.random()*10000, lng: wgsLng, lat: wgsLat, radiusMeters: obs.radiusMeters, name: obs.name });
    });
    
    // 地图图层引用
    let startMarker, endMarker;
    let routeLineSource = null;
    let obstacleSources = [];
    
    // 渲染障碍物圆
    function renderObstacles() {
        // 清除旧的障碍物图层
        obstacles.forEach(obs => {
            if (map.getSource(`obstacle-${obs.id}`)) map.removeLayer(`obstacle-fill-${obs.id}`).removeSource(`obstacle-${obs.id}`);
        });
        obstacles.forEach(obs => {
            const sourceId = `obstacle-${obs.id}`;
            const fillId = `obstacle-fill-${obs.id}`;
            const outlineId = `obstacle-outline-${obs.id}`;
            // 将半径度数近似转换 (米转度简单, 1度≈111km)
            const radiusDeg = obs.radiusMeters / 111000;
            const circlePoints = generateCirclePoints(obs.lng, obs.lat, radiusDeg);
            map.addSource(sourceId, {
                type: 'geojson',
                data: {
                    type: 'Feature',
                    geometry: { type: 'Polygon', coordinates: [circlePoints] }
                }
            });
            map.addLayer({
                id: fillId,
                type: 'fill',
                source: sourceId,
                paint: { 'fill-color': '#ff4444', 'fill-opacity': 0.45, 'fill-outline-color': '#ff0000' }
            });
            map.addLayer({
                id: outlineId,
                type: 'line',
                source: sourceId,
                paint: { 'line-color': '#ff0000', 'line-width': 2, 'line-dasharray': [2,2] }
            });
        });
        updateObstacleListUI();
    }
    
    function generateCirclePoints(lng, lat, radiusDeg, points=32) {
        let coords = [];
        for(let i=0; i<=points; i++) {
            let angle = (i * 360 / points) * Math.PI/180;
            let dx = radiusDeg * Math.cos(angle);
            let dy = radiusDeg * Math.sin(angle);
            coords.push([lng + dx, lat + dy]);
        }
        return coords;
    }
    
    function updateObstacleListUI() {
        const container = document.getElementById('obstacleList');
        if(!container) return;
        if(obstacles.length === 0) {
            container.innerHTML = '<div style="color:#64748b; text-align:center;">暂无障碍物，点击地图圈选添加</div>';
            return;
        }
        container.innerHTML = obstacles.map(obs => `
            <div class="obstacle-item">
                <div><span class="obstacle-badge"></span> ${obs.name || '障碍物'} (半径${obs.radiusMeters}m)</div>
                <button class="remove-obstacle" data-id="${obs.id}" style="background:#ef4444; padding:2px 8px;">删除</button>
            </div>
        `).join('');
        document.querySelectorAll('.remove-obstacle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = parseFloat(btn.dataset.id);
                obstacles = obstacles.filter(obs => obs.id !== id);
                renderObstacles();
                drawRouteLine(); // 重绘航线
            });
        });
    }
    
    // 绘制航线连线 (基于起点终点WGS84)
    function drawRouteLine() {
        if(!waypoints.start || !waypoints.end) return;
        if(routeLineSource && map.getSource('route-line')) map.removeLayer('route-line').removeSource('route-line');
        const geojson = {
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: [[waypoints.start.lng, waypoints.start.lat], [waypoints.end.lng, waypoints.end.lat]]
            }
        };
        map.addSource('route-line', { type: 'geojson', data: geojson });
        map.addLayer({
            id: 'route-line',
            type: 'line',
            source: 'route-line',
            paint: { 'line-color': '#3b82f6', 'line-width': 4, 'line-dasharray': [6,4] }
        });
        // 调整视野
        if(waypoints.start && waypoints.end) {
            const bounds = new mapboxgl.LngLatBounds()
                .extend([waypoints.start.lng, waypoints.start.lat])
                .extend([waypoints.end.lng, waypoints.end.lat]);
            map.fitBounds(bounds, { padding: 80, pitch: 55 });
        }
    }
    
    function updateMarkers() {
        if(startMarker) startMarker.remove();
        if(endMarker) endMarker.remove();
        if(waypoints.start) {
            startMarker = new mapboxgl.Marker({ color: '#10b981', scale: 0.9 })
                .setLngLat([waypoints.start.lng, waypoints.start.lat])
                .setPopup(new mapboxgl.Popup().setHTML(`<b>起点A</b><br/>WGS84: ${waypoints.start.lat.toFixed(5)}, ${waypoints.start.lng.toFixed(5)}`))
                .addTo(map);
        }
        if(waypoints.end) {
            endMarker = new mapboxgl.Marker({ color: '#ef4444', scale: 0.9 })
                .setLngLat([waypoints.end.lng, waypoints.end.lat])
                .setPopup(new mapboxgl.Popup().setHTML(`<b>终点B</b><br/>WGS84: ${waypoints.end.lat.toFixed(5)}, ${waypoints.end.lng.toFixed(5)}`))
                .addTo(map);
        }
        drawRouteLine();
    }
    
    // 设置点逻辑
    function setPoint(type) {
        let latInput, lngInput, coordTypeSelect;
        if(type === 'start') {
            latInput = document.getElementById('startLat');
            lngInput = document.getElementById('startLng');
            coordTypeSelect = document.getElementById('startCoordType');
        } else {
            latInput = document.getElementById('endLat');
            lngInput = document.getElementById('endLng');
            coordTypeSelect = document.getElementById('endCoordType');
        }
        const wgs = convertInputToWGS84(latInput.value, lngInput.value, coordTypeSelect.value);
        if(!wgs) { alert('请输入有效坐标'); return; }
        const [wlat, wlng] = wgs;
        if(type === 'start') waypoints.start = { lat: wlat, lng: wlng };
        else waypoints.end = { lat: wlat, lng: wlng };
        updateMarkers();
        if(type === 'start') alert(`起点A已设置 (WGS84: ${wlat.toFixed(5)}, ${wlng.toFixed(5)})`);
        else alert(`终点B已设置 (WGS84: ${wlat.toFixed(5)}, ${wlng.toFixed(5)})`);
    }
    
    // 添加障碍物交互（点击地图圈选）
    function enableObstacleMode() {
        obstacleMode = !obstacleMode;
        const btn = document.getElementById('toggleAddObstacleMode');
        if(obstacleMode) {
            btn.style.background = '#ef4444';
            btn.innerHTML = '<i class="fas fa-times"></i> 退出添加模式';
            map.getCanvas().style.cursor = 'crosshair';
        } else {
            btn.style.background = '';
            btn.innerHTML = '<i class="fas fa-plus-circle"></i> 添加障碍物模式';
            map.getCanvas().style.cursor = '';
        }
    }
    
    function handleMapClick(e) {
        if(!obstacleMode) return;
        const { lng, lat } = e.lngLat;
        const radius = 25; // 默认半径25米
        const newObs = {
            id: Date.now(),
            lng: lng,
            lat: lat,
            radiusMeters: radius,
            name: `用户障碍物${obstacles.length+1}`
        };
        obstacles.push(newObs);
        renderObstacles();
        drawRouteLine();
        obstacleMode = false;
        const btn = document.getElementById('toggleAddObstacleMode');
        btn.style.background = '';
        btn.innerHTML = '<i class="fas fa-plus-circle"></i> 添加障碍物模式';
        map.getCanvas().style.cursor = '';
        alert('障碍物已添加，半径25米，可删除或继续圈选');
    }
    
    // 心跳包模拟
    function startHeartbeat() {
        if(heartbeatInterval) clearInterval(heartbeatInterval);
        const logDiv = document.getElementById('heartbeatLog');
        document.getElementById('heartbeatStatus').innerText = '模拟接收中';
        heartbeatInterval = setInterval(() => {
            // 模拟心跳包数据: 无人机位置在校园附近移动（随机偏移展示）
            const baseLat = 32.2332, baseLng = 118.749;
            const offsetLat = (Math.random() - 0.5) * 0.002;
            const offsetLng = (Math.random() - 0.5) * 0.002;
            let simGcjLat = baseLat + offsetLat;
            let simGcjLng = baseLng + offsetLng;
            const altitude = Math.floor(Math.random() * 80 + 20);
            const speed = (Math.random() * 8).toFixed(1);
            const time = new Date().toLocaleTimeString();
            const heartItem = document.createElement('div');
            heartItem.className = 'heartbeat-item';
            heartItem.innerHTML = `<i class="fas fa-microchip"></i> [${time}] 高度:${altitude}m 速度:${speed}m/s <br/> 📍 GCJ02: ${simGcjLat.toFixed(5)}, ${simGcjLng.toFixed(5)} | 电池:${Math.floor(70+Math.random()*25)}%`;
            logDiv.prepend(heartItem);
            if(logDiv.children.length > 30) logDiv.removeChild(logDiv.lastChild);
        }, 1000);
    }
    
    function stopHeartbeat() {
        if(heartbeatInterval) { clearInterval(heartbeatInterval); heartbeatInterval=null; }
        document.getElementById('heartbeatStatus').innerText = '已停止';
    }
    
    function clearHeartbeatLog() {
        const logDiv = document.getElementById('heartbeatLog');
        logDiv.innerHTML = '<div style="text-align:center; padding:20px; color:#94a3b8;">心跳日志已清空</div>';
    }
    
    // 页面切换
    function switchPage(pageId) {
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active-page'));
        document.getElementById(`${pageId}-page`).classList.add('active-page');
        document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`.nav-btn[data-page="${pageId}"]`).classList.add('active');
        if(pageId === 'route-planning' && map) setTimeout(() => map.resize(), 150);
    }
    
    // 清理所有障碍物
    function clearObstacles() {
        obstacles = [];
        renderObstacles();
        drawRouteLine();
    }
    
    // 初始化加载预置障碍物渲染
    map.on('load', () => {
        renderObstacles();
        // 设置示例默认A/B点 (GCJ-02输入的校园点)
        setTimeout(() => {
            setPoint('start');
            setPoint('end');
        }, 500);
        map.on('click', handleMapClick);
    });
    
    // 绑定UI事件
    document.getElementById('setStartBtn').addEventListener('click', () => setPoint('start'));
    document.getElementById('setEndBtn').addEventListener('click', () => setPoint('end'));
    document.getElementById('toggleAddObstacleMode').addEventListener('click', enableObstacleMode);
    document.getElementById('clearAllObstacles').addEventListener('click', clearObstacles);
    document.getElementById('startHeartbeatSim').addEventListener('click', startHeartbeat);
    document.getElementById('stopHeartbeatSim').addEventListener('click', stopHeartbeat);
    document.getElementById('clearHeartbeat').addEventListener('click', clearHeartbeatLog);
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => switchPage(btn.dataset.page));
    });
    
    // 确保飞行高度参数展示用途
    console.log("系统就绪，支持坐标系转换，3D地图，障碍物圈选，心跳包已集成");
</script>
</body>
</html>
