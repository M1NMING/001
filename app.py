# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 3D卫星地图", layout="wide")

# ==================== 障碍物（校园内 GCJ-02 坐标，已校准）====================
OBSTACLES = [
    {"name": "图书馆", "lng": 118.7498, "lat": 32.2335},
    {"name": "教学楼", "lng": 118.7503, "lat": 32.2340},
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

# ==================== 生成地图 HTML (Leaflet + Esri 卫星图，垂直俯瞰) ====================
def generate_map_html(A_lng, A_lat, B_lng, B_lat, obstacles, flight_height):
    """返回包含地图的 HTML 字符串，使用 Leaflet 和 Esri 卫星图层"""
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
    <title>南京科技职业学院 无人机航线规划</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .marker-icon {{
            background: none;
            border: none;
            font-size: 24px;
            text-shadow: 1px 1px 0px black;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="info" style="position: absolute; top: 20px; left: 20px; z-index: 1000; background: rgba(0,0,0,0.6); color: white; padding: 5px 10px; border-radius: 5px; font-size: 12px; pointer-events: none;">
        ✈️ 航线: A → B | 飞行高度: {flight_height}m
    </div>
    <script>
        // 初始化地图 (垂直俯瞰，无倾斜)
        var map = L.map('map').setView([{center_lat}, {center_lng}], 16.5);
        
        // 添加 Esri 高分辨率卫星图 (免费，无需API Key)
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Tiles &copy; Esri',
            maxZoom: 19
        }}).addTo(map);
        
        // 起点 A 标记 (使用自定义图标)
        var markerA = L.marker([{A_lat}, {A_lng}], {{
            icon: L.divIcon({{ html: '🚁', iconSize: [28,28], className: 'marker-icon' }})
        }}).bindPopup('<b>起点 A</b><br>纬度: {A_lat}<br>经度: {A_lng}').addTo(map);
        
        // 终点 B 标记
        var markerB = L.marker([{B_lat}, {B_lng}], {{
            icon: L.divIcon({{ html: '🏁', iconSize: [28,28], className: 'marker-icon' }})
        }}).bindPopup('<b>终点 B</b><br>纬度: {B_lat}<br>经度: {B_lng}').addTo(map);
        
        // 障碍物标记
        var obstaclesData = {obstacles_js};
        for (var obs of obstaclesData) {{
            L.marker([obs.lat, obs.lng], {{
                icon: L.divIcon({{ html: '⚠️', iconSize: [24,24], className: 'marker-icon' }})
            }}).bindPopup('<b>' + obs.name + '</b><br>障碍物').addTo(map);
        }}
        
        // 绘制航线连线
        L.polyline([[{A_lat}, {A_lng}], [{B_lat}, {B_lng}]], {{
            color: '#00FFFF',
            weight: 4,
            opacity: 0.9,
            lineJoin: 'round'
        }}).addTo(map);
        
        // 自动调整视野包含所有点
        var bounds = L.latLngBounds([[{A_lat}, {A_lng}], [{B_lat}, {B_lng}]]);
        obstaclesData.forEach(obs => bounds.extend([obs.lat, obs.lng]));
        map.fitBounds(bounds, {{ padding: [50, 50] }});
    </script>
</body>
</html>
    """
    return html_code

# ==================== 主应用 ====================
def main():
    # 侧边栏导航
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (3D卫星图)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    st.sidebar.info("🗺️ 地图使用 Esri 卫星影像 (免费) | 垂直俯瞰视角")
    
    # 初始化会话状态 (坐标使用 GCJ-02)
    if "A_lat" not in st.session_state:
        st.session_state.A_lat = 32.2322
        st.session_state.A_lng = 118.7490
        st.session_state.B_lat = 32.2343
        st.session_state.B_lng = 118.7490
        st.session_state.flight_height = 50
    
    if page == "🗺️ 航线规划 (3D卫星图)":
        # 左右两列布局: 地图占70%，控制面板占30%
        left_col, right_col = st.columns([7, 3])
        
        with right_col:
            st.markdown("### 🎮 控制面板")
            st.markdown("**输入坐标系: GCJ-02 (高德/百度)**")
            
            st.markdown("#### 🚁 起点 A")
            a_lat = st.number_input("纬度 (A)", value=st.session_state.A_lat, format="%.6f", key="a_lat")
            a_lng = st.number_input("经度 (A)", value=st.session_state.A_lng, format="%.6f", key="a_lng")
            if st.button("✅ 设置 A 点", key="set_a"):
                st.session_state.A_lat = a_lat
                st.session_state.A_lng = a_lng
                st.success("A 点已更新")
            
            st.markdown("#### 📍 终点 B")
            b_lat = st.number_input("纬度 (B)", value=st.session_state.B_lat, format="%.6f", key="b_lat")
            b_lng = st.number_input("经度 (B)", value=st.session_state.B_lng, format="%.6f", key="b_lng")
            if st.button("✅ 设置 B 点", key="set_b"):
                st.session_state.B_lat = b_lat
                st.session_state.B_lng = b_lng
                st.success("B 点已更新")
            
            st.markdown("#### ✈️ 飞行参数")
            flight_height = st.number_input("飞行高度 (m)", value=st.session_state.flight_height, step=5)
            st.session_state.flight_height = flight_height
            
            st.markdown("---")
            st.markdown("#### 🧱 障碍物列表 (校园内)")
            for obs in OBSTACLES:
                st.write(f"- {obs['name']}: ({obs['lng']}, {obs['lat']})")
        
        with left_col:
            st.markdown("### 🗺️ 3D 卫星地图 (垂直俯瞰)")
            # 生成地图 HTML 并嵌入
            map_html = generate_map_html(
                st.session_state.A_lng, st.session_state.A_lat,
                st.session_state.B_lng, st.session_state.B_lat,
                OBSTACLES, st.session_state.flight_height
            )
            html(map_html, height=650, scrolling=False)
    
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
