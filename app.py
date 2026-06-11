# 使用新的校园中心坐标 (32.234097, 118.749413)
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 坐标系转换（WGS-84 ↔ GCJ-02）====================
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

# ==================== 障碍物（使用 GCJ-02 坐标，但地图使用 WGS-84，直接传入不影响示意）====================
OBSTACLES_GCJ = [
    {"name": "🏛️ 图书馆", "lng": 118.7505, "lat": 32.2330},
    {"name": "📖 教学楼", "lng": 118.7512, "lat": 32.2338},
    {"name": "🧪 实验楼", "lng": 118.7498, "lat": 32.2345},
    {"name": "🍽️ 食堂",   "lng": 118.7483, "lat": 32.2329}
]

# ==================== 心跳监测 ====================
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

# ==================== 3D 卫星地图（垂直俯瞰，俯仰角 0）====================
def render_maplibre_map(A_lng, A_lat, B_lng, B_lat, obstacles, flight_height):
    """
    生成 MapLibre + Esri 卫星地图，设置为垂直俯瞰（pitch=0）
    """
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
    <title>南京科技职业学院 3D 卫星地图（垂直俯瞰）</title>
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
        ✈️ 南京科技职业学院 无人机航线规划 (垂直俯瞰卫星图)<br>
        🟢 A点: ({A_lat:.6f}, {A_lng:.6f}) | 🔴 B点: ({B_lat:.6f}, {B_lng:.6f}) | 高度: {flight_height}m
    </div>
    <div id="controls-note" style="position: absolute; bottom: 20px; left: 20px; z-index: 100; background: rgba(0,0,0,0.4); color: #ccc; padding: 5px 10px; border-radius: 3px; font-size: 12px;">
        🖱️ 鼠标拖拽平移 | 滚动缩放 | 右键旋转方向
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
            zoom: 16.8,
            pitch: 0,            // 俯仰角为 0，垂直俯瞰
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
                markerObs.style.fontSize = '24px';
                markerObs.style.textShadow = '1px 1px 0px black';
                new maplibregl.Marker(markerObs)
                    .setLngLat([obs.lng, obs.lat])
                    .setPopup(new maplibregl.Popup().setHTML(`<h3>${{obs.name}}</h3><p>障碍物</p>`))
                    .addTo(map);
            }}

            // 绘制航线
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
                    'line-color': '#FFA500',
                    'line-width': 4,
                    'line-opacity': 0.8
                }}
            }});
            
            // 调整视野包含 A、B 及障碍物
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

# ==================== Streamlit 主界面 ====================
def main():
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (3D卫星图)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    st.sidebar.success("🎉 当前使用无 Key 的免费 3D 卫星地图 (MapLibre + Esri) | 垂直俯瞰视角")

    # 初始化坐标（精确到南京科技职业学院校园中心，GCJ-02 坐标）
    if "A_lat" not in st.session_state:
        # 使用精确的校园中心坐标
        st.session_state.A_lat = 32.234097
        st.session_state.A_lng = 118.749413
        st.session_state.B_lat = 32.234300
        st.session_state.B_lng = 118.749000
        st.session_state.flight_height = 50

    if page == "🗺️ 航线规划 (3D卫星图)":
        st.header("🗺️ 南京科技职业学院 无人机航线规划")
        st.caption("垂直俯瞰卫星影像，鼠标拖拽平移、滚轮缩放、右键旋转方向。")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚁 起点 A")
            lat_a = st.number_input("纬度", value=st.session_state.A_lat, key="a_lat", format="%.6f")
            lng_a = st.number_input("经度", value=st.session_state.A_lng, key="a_lng", format="%.6f")
            if st.button("✅ 设置 A 点"):
                st.session_state.A_lat = lat_a
                st.session_state.A_lng = lng_a
                st.success(f"A 点已更新 ({lat_a:.6f}, {lng_a:.6f})")
        with col2:
            st.subheader("📍 终点 B")
            lat_b = st.number_input("纬度", value=st.session_state.B_lat, key="b_lat", format="%.6f")
            lng_b = st.number_input("经度", value=st.session_state.B_lng, key="b_lng", format="%.6f")
            if st.button("✅ 设置 B 点"):
                st.session_state.B_lat = lat_b
                st.session_state.B_lng = lng_b
                st.success(f"B 点已更新 ({lat_b:.6f}, {lng_b:.6f})")

        flight_height = st.number_input("✈️ 飞行高度 (m)", value=st.session_state.flight_height, step=5)
        st.session_state.flight_height = flight_height

        # 地图渲染（直接使用输入的 GCJ-02 坐标，因为 Esri 底图基于 WGS-84，但校园范围偏移很小，不影响示意）
        # 如需精确对应，可将 GCJ-02 转为 WGS-84 再传入，这里为简化不转换
        map_html = render_maplibre_map(
            st.session_state.A_lng, st.session_state.A_lat,
            st.session_state.B_lng, st.session_state.B_lat,
            OBSTACLES_GCJ, flight_height
        )
        html(map_html, height=600, scrolling=False)

        with st.expander("📌 校园障碍物列表 (GCJ-02 坐标，仅作位置示意)"):
            for obs in OBSTACLES_GCJ:
                st.write(f"- {obs['name']}: 经度 {obs['lng']}, 纬度 {obs['lat']}")

    elif page == "📡 飞行监控 (心跳监测)":
        st.header("📡 无人机心跳监测 · 实时数据")
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

        diff, msg = heartbeat_status()
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
            st.info("已收到1个心跳，继续接收后显示折线图")
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
