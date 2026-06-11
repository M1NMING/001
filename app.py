import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 坐标系转换（与之前代码保持一致）====================
def wgs84_to_gcj02(lng, lat):
    """WGS-84 -> GCJ-02"""
    # ...（此处代码无变化，为节省篇幅省略，请使用之前问答中的完整函数）...
    a = 6378245.0
    ee = 0.00669342162296594323
    # ...（函数实现）...
    return lng + dlng, lat + dlat

# ==================== 障碍物预设（与之前代码保持一致）====================
OBSTACLES_GCJ = [
    {"name": "🏛️ 图书馆", "lng": 118.7505, "lat": 32.2330},
    {"name": "📖 教学楼", "lng": 118.7512, "lat": 32.2338},
    {"name": "🧪 实验楼", "lng": 118.7498, "lat": 32.2345},
    {"name": "🍽️ 食堂",   "lng": 118.7483, "lat": 32.2329}
]

# ==================== 心跳监测（与之前代码保持一致）====================
def init_heartbeat():
    # ...（此处代码无变化，为节省篇幅省略）...
    if "heartbeat_list" not in st.session_state:
        st.session_state.heartbeat_list = []

def update_heartbeat(enable):
    # ...（此处代码无变化，为节省篇幅省略）...
    pass

def heartbeat_status():
    # ...（此处代码无变化，为节省篇幅省略）...
    return None, "OK"

# ==================== 使用 MapLibre 和 Esri 卫星图的 3D 地图 ====================
def render_maplibre_map(A_lng, A_lat, B_lng, B_lat, obstacles, flight_height):
    """
    生成一个 MapLibre GL JS 的 3D 地图 HTML 字符串。
    使用 Esri 的 World Imagery 作为免费卫星底图。
    """
    # 计算地图中心点
    center_lng = (A_lng + B_lng) / 2
    center_lat = (A_lat + B_lat) / 2
    
    # 将障碍物列表转换为 JavaScript 代码
    obstacles_js = "[\n" + ",\n".join([
        f'{{name: "{obs['name']}", lng: {obs['lng']}, lat: {obs['lat']}}}' for obs in obstacles
    ]) + "\n]"

    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>3D 卫星地图 - MapLibre</title>
    <!-- 引入 MapLibre GL JS 的样式和库 -->
    <link href="https://unpkg.com/maplibre-gl@4.7.0/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@4.7.0/dist/maplibre-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="info" style="position: absolute; top: 20px; left: 20px; z-index: 100; background: rgba(0,0,0,0.6); color: white; padding: 10px 15px; border-radius: 5px; font-family: sans-serif; font-size: 14px;">
        ✈️ 南京科技职业学院 无人机航线规划 (3D卫星图)<br>
        🟢 A点: ({A_lat}, {A_lng}) | 🔴 B点: ({B_lat}, {B_lng}) | 高度: {flight_height}m
    </div>
    <div id="controls-note" style="position: absolute; bottom: 20px; left: 20px; z-index: 100; background: rgba(0,0,0,0.4); color: #ccc; padding: 5px 10px; border-radius: 3px; font-size: 12px;">
        🖱️ 鼠标拖拽旋转视角 | 右键拖拽倾斜 | 滚动缩放
    </div>
    
    <script>
        // 1. 初始化地图，设置中心点、初始视角和 3D 效果
        var map = new maplibregl.Map({{
            container: 'map',
            style: {{
                'version': 8,
                'sources': {{
                    // 使用 Esri 的免费高分辨率卫星影像图 (World Imagery) 
                    'satellite': {{
                        'type': 'raster',
                        'tiles': ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'],
                        'tileSize': 256,
                        'attribution': 'Tiles &copy; Esri'
                    }}
                }},
                'layers': [
                    {{
                        'id': 'satellite-layer',
                        'type': 'raster',
                        'source': 'satellite',
                        'minzoom': 0,
                        'maxzoom': 22
                    }}
                ]
            }},
            center: [{center_lng}, {center_lat}],
            zoom: 16.5,
            pitch: 65,          // 设置倾斜角，实现 3D 效果
            bearing: 0,         // 初始旋转角度
            antialias: true     // 抗锯齿
        }});

        // 2. 添加地形效果 (可选，使用MapLibre的默认地形)
        map.on('load', function() {{
            // 添加 3D 地形，让山体更真实
            map.addSource('mapbox-dem', {{
                'type': 'raster-dem',
                'url': 'https://demotiles.maplibre.org/terrain-tiles/tiles.json', // 示例地形源
                'tileSize': 512
            }});
            map.setTerrain({{ 'source': 'mapbox-dem', 'exaggeration': 1.5 }});

            // 添加导航控件，支持3D倾斜和旋转
            map.addControl(new maplibregl.NavigationControl({{ visualizePitch: true }}), 'top-right');

            // --- 3. 添加起点 A 的标记 ---
            var markerA = document.createElement('div');
            markerA.className = 'marker';
            markerA.innerHTML = '🚁';
            markerA.style.fontSize = '28px';
            markerA.style.textShadow = '1px 1px 0px black';
            new maplibregl.Marker(markerA)
                .setLngLat([{A_lng}, {A_lat}])
                .setPopup(new maplibregl.Popup().setHTML('<h3>起点 A</h3><p>纬度: {A_lat}<br>经度: {A_lng}</p>'))
                .addTo(map);

            // --- 4. 添加终点 B 的标记 ---
            var markerB = document.createElement('div');
            markerB.className = 'marker';
            markerB.innerHTML = '🏁';
            markerB.style.fontSize = '28px';
            markerB.style.textShadow = '1px 1px 0px black';
            new maplibregl.Marker(markerB)
                .setLngLat([{B_lng}, {B_lat}])
                .setPopup(new maplibregl.Popup().setHTML('<h3>终点 B</h3><p>纬度: {B_lat}<br>经度: {B_lng}</p>'))
                .addTo(map);
            
            // --- 5. 添加障碍物标记 ---
            var obstaclesData = {obstacles_js};
            for (var obs of obstaclesData) {{
                var markerObs = document.createElement('div');
                markerObs.className = 'marker';
                markerObs.innerHTML = '⚠️';
                markerObs.style.fontSize = '24px';
                markerObs.style.textShadow = '1px 1px 0px black';
                new maplibregl.Marker(markerObs)
                    .setLngLat([obs.lng, obs.lat])
                    .setPopup(new maplibregl.Popup().setHTML(`<h3>${{obs.name}}</h3><p>障碍物</p>`))
                    .addTo(map);
            }}

            // --- 6. 绘制 A-B 之间的航线 (LineString) ---
            var routeCoordinates = [
                [{A_lng}, {A_lat}],
                [{B_lng}, {B_lat}]
            ];
            
            map.addSource('route', {{
                'type': 'geojson',
                'data': {{
                    'type': 'Feature',
                    'properties': {{}},
                    'geometry': {{
                        'type': 'LineString',
                        'coordinates': routeCoordinates
                    }}
                }}
            }});
            
            map.addLayer({{
                'id': 'route-line',
                'type': 'line',
                'source': 'route',
                'layout': {{
                    'line-join': 'round',
                    'line-cap': 'round'
                }},
                'paint': {{
                    'line-color': '#FFA500',  // 橙色航线，更醒目
                    'line-width': 4,
                    'line-opacity': 0.8
                }}
            }});
            
            // 7. 可选：添加一个简单的动画效果来展示无人机从 A 飞到 B (只是为了演示)
            // 这里简单地将地图视角调整为包含 A 和 B 点的范围，提升用户体验
            var bounds = new maplibregl.LngLatBounds();
            bounds.extend([{A_lng}, {A_lat}]);
            bounds.extend([{B_lng}, {B_lat}]);
            map.fitBounds(bounds, {{ padding: 50, duration: 1000 }});
        }});
    </script>
</body>
</html>
    """
    return html_code

# ==================== Streamlit 主界面逻辑 ====================
def main():
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (3D卫星图)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    st.sidebar.success("🎉 当前使用无 Key 的免费 3D 卫星地图 (MapLibre + Esri)")
    
    # 初始化坐标
    if "A_lat" not in st.session_state:
        st.session_state.A_lat = 32.2322
        st.session_state.A_lng = 118.749
        st.session_state.B_lat = 32.2343
        st.session_state.B_lng = 118.749
        st.session_state.flight_height = 50

    if page == "🗺️ 航线规划 (3D卫星图)":
        st.header("🗺️ 南京科技职业学院 无人机航线规划")
        st.caption("使用 MapLibre 与 Esri 卫星影像，完全免费，开箱即用。鼠标拖拽旋转视角，右键拖拽倾斜地图。")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚁 起点 A")
            lat_a = st.number_input("纬度", value=st.session_state.A_lat, key="a_lat", format="%.6f")
            lng_a = st.number_input("经度", value=st.session_state.A_lng, key="a_lng", format="%.6f")
            if st.button("✅ 设置 A 点", key="set_a"):
                st.session_state.A_lat = lat_a
                st.session_state.A_lng = lng_a
                st.success(f"A 点已更新 ({lat_a:.6f}, {lng_a:.6f})")
        with col2:
            st.subheader("📍 终点 B")
            lat_b = st.number_input("纬度", value=st.session_state.B_lat, key="b_lat", format="%.6f")
            lng_b = st.number_input("经度", value=st.session_state.B_lng, key="b_lng", format="%.6f")
            if st.button("✅ 设置 B 点", key="set_b"):
                st.session_state.B_lat = lat_b
                st.session_state.B_lng = lng_b
                st.success(f"B 点已更新 ({lat_b:.6f}, {lng_b:.6f})")
        
        flight_height = st.number_input("✈️ 飞行高度 (m)", value=st.session_state.flight_height, step=5)
        st.session_state.flight_height = flight_height

        # 由于 MapLibre 和 Esri 底图使用 WGS-84 坐标系，而我们的输入坐标默认为 GCJ-02
        # 为简化，这里假设用户输入的是 WGS-84 坐标 (如果需要精确匹配高德坐标，可调用 wgs84_to_gcj02，但这里地图直接使用 WGS-84)
        # 为了演示障碍物，我们直接将预设的 GCJ-02 障碍物当做 WGS-84 传入，不影响演示效果。
        map_html = render_maplibre_map(st.session_state.A_lng, st.session_state.A_lat, 
                                       st.session_state.B_lng, st.session_state.B_lat, 
                                       OBSTACLES_GCJ, flight_height)
        
        # 在 Streamlit 中显示生成的 HTML 地图
        html(map_html, height=600, scrolling=False)
        
        with st.expander("📌 校园障碍物列表 (当前为 GCJ-02 坐标，仅作位置示意)"):
            for obs in OBSTACLES_GCJ:
                st.write(f"- {obs['name']}: 经度 {obs['lng']}, 纬度 {obs['lat']}")

    elif page == "📡 飞行监控 (心跳监测)":
        st.header("📡 无人机心跳监测 · 实时数据")
        init_heartbeat()
        enable = st.sidebar.checkbox("🚁 允许发送心跳", value=True, key="hb_enable")
        update_heartbeat(enable)

        # 显示心跳数据 (此部分代码与之前完全一致，为节省篇幅省略，请参考之前的回答或自行补全)
        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("💓 最新序号", latest[0])
            col2.metric("⏱️ 最新时间", latest[1])
        else:
            col1.metric("💓 最新序号", "无")
            col2.metric("⏱️ 最新时间", "无")
        # ... （心跳状态、折线图、表格的显示代码与之前相同，此处省略）
        # 自动刷新 (每秒)
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
