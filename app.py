# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 3D卫星地图 + 心跳监测", layout="wide")

# ==================== 坐标系转换 (WGS-84 ↔ GCJ-02) ====================
def wgs84_to_gcj02(lng, lat):
    """WGS-84 → GCJ-02"""
    a = 6378245.0
    ee = 0.00669342162296594323

    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
        ret += 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret

    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y
        ret += 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat

def gcj02_to_wgs84(lng, lat):
    """GCJ-02 → WGS-84 近似转换"""
    # 使用简单偏差法（精度足够）
    wgs_lng, wgs_lat = wgs84_to_gcj02(lng, lat)
    return 2*lng - wgs_lng, 2*lat - wgs_lat

# ==================== 真实校园障碍物 (GCJ-02 坐标，确保在校区内) ====================
# 根据南京科技职业学院实际建筑位置标定
OBSTACLES_GCJ = [
    {"name": "图书馆", "lng": 118.7498, "lat": 32.2335},
    {"name": "教学楼1", "lng": 118.7503, "lat": 32.2340},
    {"name": "实验楼", "lng": 118.7489, "lat": 32.2338},
    {"name": "食堂",   "lng": 118.7485, "lat": 32.2328}
]

# ==================== 心跳监测模块 ====================
def init_heartbeat():
    if "heartbeat_list" not in st.session_state:
        st.session_state.heartbeat_list = []
    if "last_gen_time" not in st.session_state:
        st.session_state.last_gen_time = None
    if "seq_counter" not in st.session_state:
        st.session_state.seq_counter = 0

def update_heartbeat(enable):
    now = datetime.now()
    if enable:
        if (st.session_state.last_gen_time is None or
            (now - st.session_state.last_gen_time).total_seconds() >= 1):
            st.session_state.seq_counter += 1
            st.session_state.heartbeat_list.append(
                [st.session_state.seq_counter, now.strftime("%H:%M:%S"), now])
            st.session_state.last_gen_time = now
            if len(st.session_state.heartbeat_list) > 300:
                st.session_state.heartbeat_list.pop(0)

def heartbeat_status():
    if not st.session_state.heartbeat_list:
        return None, "⏳ 等待首个心跳包..."
    last = st.session_state.heartbeat_list[-1][2]
    diff = (datetime.now() - last).total_seconds()
    if diff > 3:
        return diff, f"⚠️ 连接超时！已 {diff:.1f} 秒未收到心跳包"
    else:
        return diff, f"✅ 连接正常，最后心跳: {diff:.1f} 秒前"

# ==================== 生成地图 HTML (MapLibre + Esri 卫星图，垂直俯瞰) ====================
def generate_map_html(A_lng, A_lat, B_lng, B_lat, obstacles, flight_height):
    """返回包含地图的 HTML 字符串，输入坐标为 WGS-84"""
    center_lng = (A_lng + B_lng) / 2
    center_lat = (A_lat + B_lat) / 2

    obstacles_js = "[\n" + ",\n".join([
        f'{{name: "{obs['name']}", lng: {obs['lng']}, lat: {obs['lat']}}}' for obs in obstacles
    ]) + "\n]"

    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>南京科技职业学院 3D 卫星地图</title>
    <link href="https://unpkg.com/maplibre-gl@4.7.0/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@4.7.0/dist/maplibre-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100%; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="info" style="position: absolute; top: 20px; left: 20px; z-index: 100; background: rgba(0,0,0,0.6); color: white; padding: 8px 12px; border-radius: 5px; font-size: 12px; pointer-events: none;">
        ✈️ 航线: A → B | 高度: {flight_height}m
    </div>
    <script>
        var map = new maplibregl.Map({{
            container: 'map',
            style: {{
                'version': 8,
                'sources': {{
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
            pitch: 0,            // 垂直俯瞰，二维平面效果
            bearing: 0,
            antialias: true
        }});

        map.on('load', function() {{
            map.addControl(new maplibregl.NavigationControl({{ visualizePitch: false }}), 'top-right');

            // 起点 A 标记
            var markerA = document.createElement('div');
            markerA.innerHTML = '🚁';
            markerA.style.fontSize = '28px';
            markerA.style.textShadow = '1px 1px 0px black';
            new maplibregl.Marker(markerA)
                .setLngLat([{A_lng}, {A_lat}])
                .setPopup(new maplibregl.Popup().setHTML('<h3>起点 A</h3><p>纬度: {A_lat}<br>经度: {A_lng}</p>'))
                .addTo(map);

            // 终点 B 标记
            var markerB = document.createElement('div');
            markerB.innerHTML = '🏁';
            markerB.style.fontSize = '28px';
            markerB.style.textShadow = '1px 1px 0px black';
            new maplibregl.Marker(markerB)
                .setLngLat([{B_lng}, {B_lat}])
                .setPopup(new maplibregl.Popup().setHTML('<h3>终点 B</h3><p>纬度: {B_lat}<br>经度: {B_lng}</p>'))
                .addTo(map);
            
            // 障碍物标记
            var obstaclesData = {obstacles_js};
            for (var obs of obstaclesData) {{
                var markerObs = document.createElement('div');
                markerObs.innerHTML = '⚠️';
                markerObs.style.fontSize = '22px';
                markerObs.style.textShadow = '1px 1px 0px black';
                new maplibregl.Marker(markerObs)
                    .setLngLat([obs.lng, obs.lat])
                    .setPopup(new maplibregl.Popup().setHTML(`<h3>${{obs.name}}</h3><p>障碍物</p>`))
                    .addTo(map);
            }}

            // 航线连线
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
                'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
                'paint': {{
                    'line-color': '#00FFFF',
                    'line-width': 4,
                    'line-opacity': 0.9
                }}
            }});

            // 自动调整视野
            var bounds = new maplibregl.LngLatBounds();
            bounds.extend([{A_lng}, {A_lat}]);
            bounds.extend([{B_lng}, {B_lat}]);
            obstaclesData.forEach(obs => bounds.extend([obs.lng, obs.lat]));
            map.fitBounds(bounds, {{ padding: 50, duration: 1000 }});
        }});
    </script>
</body>
</html>
    """
    return html_code

# ==================== 主应用 ====================
def main():
    # 侧边栏页面选择
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (3D卫星图)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    st.sidebar.info("地图使用 Esri 卫星影像 (免费) | 垂直俯瞰视角")

    # 初始化会话状态
    if "A_lat_gcj" not in st.session_state:
        # 校园内合理的 GCJ-02 坐标
        st.session_state.A_lat_gcj = 32.2322
        st.session_state.A_lng_gcj = 118.7490
        st.session_state.B_lat_gcj = 32.2343
        st.session_state.B_lng_gcj = 118.7490
        st.session_state.flight_height = 50
        st.session_state.coord_sys = "GCJ-02"

    if page == "🗺️ 航线规划 (3D卫星图)":
        # 左右两列布局：地图占70%，控制面板占30%
        left_col, right_col = st.columns([7, 3])

        with right_col:
            st.markdown("### 🎮 控制面板")
            # 坐标系选择
            coord_sys = st.selectbox("输入坐标系", ["GCJ-02", "WGS-84"], index=0, key="coord_selector")
            st.session_state.coord_sys = coord_sys

            st.markdown("#### 🚁 起点 A")
            a_lat = st.number_input("纬度 (A)", value=st.session_state.A_lat_gcj, format="%.6f", key="a_lat")
            a_lng = st.number_input("经度 (A)", value=st.session_state.A_lng_gcj, format="%.6f", key="a_lng")
            if st.button("✅ 设置 A 点"):
                st.session_state.A_lat_gcj = a_lat
                st.session_state.A_lng_gcj = a_lng
                st.success("A 点已更新")

            st.markdown("#### 📍 终点 B")
            b_lat = st.number_input("纬度 (B)", value=st.session_state.B_lat_gcj, format="%.6f", key="b_lat")
            b_lng = st.number_input("经度 (B)", value=st.session_state.B_lng_gcj, format="%.6f", key="b_lng")
            if st.button("✅ 设置 B 点"):
                st.session_state.B_lat_gcj = b_lat
                st.session_state.B_lng_gcj = b_lng
                st.success("B 点已更新")

            st.markdown("#### ✈️ 飞行参数")
            flight_height = st.number_input("飞行高度 (m)", value=st.session_state.flight_height, step=5)
            st.session_state.flight_height = flight_height

            st.markdown("---")
            st.markdown("#### 🧱 障碍物列表 (校园内)")
            for obs in OBSTACLES_GCJ:
                st.write(f"- {obs['name']}: ({obs['lng']}, {obs['lat']})")

        # 地图显示在左列
        with left_col:
            st.markdown("### 🗺️ 3D 卫星地图 (垂直俯瞰)")
            # 根据用户选择的坐标系，将当前 A、B 点转换为 WGS-84（地图所需）
            if st.session_state.coord_sys == "GCJ-02":
                A_wgs_lng, A_wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
                B_wgs_lng, B_wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
            else:
                # 用户输入的是 WGS-84，直接使用
                A_wgs_lng, A_wgs_lat = st.session_state.A_lng_gcj, st.session_state.A_lat_gcj
                B_wgs_lng, B_wgs_lat = st.session_state.B_lng_gcj, st.session_state.B_lat_gcj

            # 障碍物也需要转换（障碍物存储为 GCJ-02，需要转为 WGS-84 才能在地图上准确显示）
            obstacles_wgs = []
            for obs in OBSTACLES_GCJ:
                wgs_lng, wgs_lat = gcj02_to_wgs84(obs["lng"], obs["lat"])
                obstacles_wgs.append({"name": obs["name"], "lng": wgs_lng, "lat": wgs_lat})

            map_html = generate_map_html(A_wgs_lng, A_wgs_lat, B_wgs_lng, B_wgs_lat, obstacles_wgs, flight_height)
            html(map_html, height=650, scrolling=False)

    elif page == "📡 飞行监控 (心跳监测)":
        st.header("📡 无人机心跳监测 · 实时飞行数据")
        init_heartbeat()
        enable = st.sidebar.checkbox("🚁 允许发送心跳", value=True, key="hb_enable")
        update_heartbeat(enable)

        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("💓 最新序号", latest[0])
            col2.metric("⏱️ 最新时间", latest[1])
        else:
            col1.metric("💓 最新序号", "无")
            col2.metric("⏱️ 最新时间", "无")

        _, msg = heartbeat_status()
        if "超时" in msg:
            st.error(msg)
        elif "等待" in msg:
            st.info(msg)
        else:
            st.success(msg)

        if len(st.session_state.heartbeat_list) >= 2:
            df = pd.DataFrame(st.session_state.heartbeat_list, columns=["序号", "时间", "dt"])
            fig = px.line(df, x="时间", y="序号", title="📈 心跳序号趋势", markers=True)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        elif len(st.session_state.heartbeat_list) == 1:
            st.info("已收到 1 个心跳，继续接收后显示折线图")
        else:
            st.info("等待心跳数据...")

        if st.session_state.heartbeat_list:
            df_tab = pd.DataFrame(st.session_state.heartbeat_list[-10:], columns=["序号", "时间", "dt"])
            st.dataframe(df_tab.drop(columns=["dt"]), use_container_width=True)
        else:
            st.info("暂无记录")

        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
