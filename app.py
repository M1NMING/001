# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 卫星地图 + 心跳监测", layout="wide")

# ==================== 坐标系转换 (GCJ-02 ↔ WGS-84) ====================
def wgs84_to_gcj02(lng, lat):
    """WGS-84 → GCJ-02 (火星坐标系)"""
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
    """GCJ-02 → WGS-84 近似转换（反向迭代）"""
    # 使用简单的偏移法，精度足够
    wgs_lng, wgs_lat = wgs84_to_gcj02(lng, lat)
    return 2*lng - wgs_lng, 2*lat - wgs_lat

# ==================== 预设障碍物（仅用于右侧参考，不显示在地图上）====================
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

# ==================== 生成卫星地图 HTML (Leaflet + Esri 卫星图) ====================
def generate_satellite_map(A_lng_wgs, A_lat_wgs, B_lng_wgs, B_lat_wgs, flight_height):
    """生成包含卫星影像的地图，输入坐标为 WGS-84"""
    center_lng = (A_lng_wgs + B_lng_wgs) / 2
    center_lat = (A_lat_wgs + B_lat_wgs) / 2

    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>无人机航线规划 - 卫星地图</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .marker-icon {{
            background: none;
            border: none;
            font-size: 28px;
            text-shadow: 1px 1px 0px black;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="info" style="position: absolute; top: 20px; left: 20px; z-index: 1000; background: rgba(0,0,0,0.6); color: white; padding: 5px 10px; border-radius: 5px; font-size: 12px; pointer-events: none;">
        ✈️ 航线: A → B | 飞行高度: {flight_height}m | 卫星图源: Esri
    </div>
    <div id="controls-note" style="position: absolute; bottom: 20px; left: 20px; z-index: 1000; background: rgba(0,0,0,0.4); color: #ccc; padding: 5px 10px; border-radius: 3px; font-size: 12px;">
        🖱️ 拖拽平移 | 滚轮缩放 | 垂直俯瞰
    </div>
    <script>
        // 初始化地图，设置中心点和缩放级别
        var map = L.map('map').setView([{center_lat}, {center_lng}], 16.5);
        
        // 使用 Esri 高分辨率卫星图层 (稳定免费)
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Tiles &copy; Esri',
            maxZoom: 19
        }}).addTo(map);
        
        // 起点 A 标记 (带图标)
        var markerA = L.marker([{A_lat_wgs}, {A_lng_wgs}], {{
            icon: L.divIcon({{ html: '🚁', iconSize: [30,30], className: 'marker-icon' }})
        }}).bindPopup('<b>起点 A</b><br>纬度: {A_lat_wgs:.6f}<br>经度: {A_lng_wgs:.6f}').addTo(map);
        
        // 终点 B 标记
        var markerB = L.marker([{B_lat_wgs}, {B_lng_wgs}], {{
            icon: L.divIcon({{ html: '🏁', iconSize: [30,30], className: 'marker-icon' }})
        }}).bindPopup('<b>终点 B</b><br>纬度: {B_lat_wgs:.6f}<br>经度: {B_lng_wgs:.6f}').addTo(map);
        
        // 绘制航线连线
        L.polyline([[{A_lat_wgs}, {A_lng_wgs}], [{B_lat_wgs}, {B_lng_wgs}]], {{
            color: '#00FFFF',
            weight: 4,
            opacity: 0.9,
            lineJoin: 'round'
        }}).addTo(map);
        
        // 自动调整视野包含 A 和 B 点
        var bounds = L.latLngBounds([[{A_lat_wgs}, {A_lng_wgs}], [{B_lat_wgs}, {B_lng_wgs}]]);
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
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (卫星地图)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")

    # 坐标系设置 (放在侧边栏)
    st.sidebar.subheader("坐标系设置")
    coord_sys = st.sidebar.radio("输入坐标系", ["GCJ-02 (高德/百度)", "WGS-84"], index=0)

    # 系统状态 (A/B 点是否已设)
    st.sidebar.subheader("系统状态")
    a_set = ("A_lat_gcj" in st.session_state and "A_lng_gcj" in st.session_state)
    b_set = ("B_lat_gcj" in st.session_state and "B_lng_gcj" in st.session_state)
    st.sidebar.write(f"{'✅' if a_set else '❌'} A点已设")
    st.sidebar.write(f"{'✅' if b_set else '❌'} B点已设")

    st.sidebar.markdown("---")
    st.sidebar.info("🗺️ 卫星图源: Esri World Imagery | 垂直俯瞰\n🔄 支持 GCJ-02 / WGS-84 自动转换")

    # 初始化会话状态 (所有坐标统一以 GCJ-02 存储)
    if "A_lat_gcj" not in st.session_state:
        # 默认校园内坐标 (GCJ-02)
        st.session_state.A_lat_gcj = 32.2323
        st.session_state.A_lng_gcj = 118.7490
    if "B_lat_gcj" not in st.session_state:
        st.session_state.B_lat_gcj = 32.2344
        st.session_state.B_lng_gcj = 118.7490
    if "flight_height" not in st.session_state:
        st.session_state.flight_height = 10   # 默认10米

    # ==================== 航线规划页面 ====================
    if page == "🗺️ 航线规划 (卫星地图)":
        left_col, right_col = st.columns([7, 3])

        with right_col:
            st.markdown("### 🎮 控制面板")
            st.markdown(f"**当前坐标系: {coord_sys}**")

            # ---------- 起点 A 输入 ----------
            st.markdown("#### 🚁 起点 A")
            if coord_sys == "GCJ-02 (高德/百度)":
                a_lat_input = st.number_input("纬度 (A)", value=st.session_state.A_lat_gcj, format="%.6f", key="a_lat")
                a_lng_input = st.number_input("经度 (A)", value=st.session_state.A_lng_gcj, format="%.6f", key="a_lng")
            else:  # WGS-84 → 显示时需要将存储的 GCJ-02 转为 WGS-84
                # 转换存储的 GCJ-02 到 WGS-84 显示
                wgs_lng, wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
                a_lat_input = st.number_input("纬度 (A)", value=wgs_lat, format="%.6f", key="a_lat_wgs")
                a_lng_input = st.number_input("经度 (A)", value=wgs_lng, format="%.6f", key="a_lng_wgs")

            if st.button("✅ 设置 A 点"):
                if coord_sys == "GCJ-02 (高德/百度)":
                    st.session_state.A_lat_gcj = a_lat_input
                    st.session_state.A_lng_gcj = a_lng_input
                else:
                    # WGS-84 输入 → 转为 GCJ-02 存储
                    gcj_lng, gcj_lat = wgs84_to_gcj02(a_lng_input, a_lat_input)
                    st.session_state.A_lat_gcj = gcj_lat
                    st.session_state.A_lng_gcj = gcj_lng
                st.success("A 点已更新")

            # ---------- 终点 B 输入 ----------
            st.markdown("#### 📍 终点 B")
            if coord_sys == "GCJ-02 (高德/百度)":
                b_lat_input = st.number_input("纬度 (B)", value=st.session_state.B_lat_gcj, format="%.6f", key="b_lat")
                b_lng_input = st.number_input("经度 (B)", value=st.session_state.B_lng_gcj, format="%.6f", key="b_lng")
            else:
                wgs_lng, wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
                b_lat_input = st.number_input("纬度 (B)", value=wgs_lat, format="%.6f", key="b_lat_wgs")
                b_lng_input = st.number_input("经度 (B)", value=wgs_lng, format="%.6f", key="b_lng_wgs")

            if st.button("✅ 设置 B 点"):
                if coord_sys == "GCJ-02 (高德/百度)":
                    st.session_state.B_lat_gcj = b_lat_input
                    st.session_state.B_lng_gcj = b_lng_input
                else:
                    gcj_lng, gcj_lat = wgs84_to_gcj02(b_lng_input, b_lat_input)
                    st.session_state.B_lat_gcj = gcj_lat
                    st.session_state.B_lng_gcj = gcj_lng
                st.success("B 点已更新")

            # ---------- 飞行高度 ----------
            st.markdown("#### ✈️ 飞行参数")
            flight_h = st.number_input("设定飞行高度 (m)", value=st.session_state.flight_height, step=1, min_value=0, max_value=500)
            st.session_state.flight_height = flight_h

            # ---------- 障碍物列表 (仅参考) ----------
            st.markdown("---")
            st.markdown("#### 🧱 障碍物列表 (校园内)")
            for obs in OBSTACLES:
                st.write(f"- {obs['name']}: ({obs['lng']}, {obs['lat']})")

        # ---------- 地图显示 (左列) ----------
        with left_col:
            st.markdown("### 🗺️ 卫星实况地图 (垂直俯瞰)")
            # 将存储的 GCJ-02 坐标转换为 WGS-84 供地图使用
            A_wgs_lng, A_wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
            B_wgs_lng, B_wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
            map_html = generate_satellite_map(A_wgs_lng, A_wgs_lat, B_wgs_lng, B_wgs_lat, flight_h)
            html(map_html, height=650, scrolling=False)

    # ==================== 飞行监控页面 ====================
    elif page == "📡 飞行监控 (心跳监测)":
        st.header("📡 无人机心跳监测 · 实时数据")
        init_heartbeat()
        enable = st.sidebar.checkbox("🚁 允许无人机发送心跳包", value=True, key="hb_enable")
        update_heartbeat(enable)

        # 显示最新心跳信息
        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("💓 最新心跳序号", latest[0])
            col2.metric("⏱️ 最新心跳时间", latest[1])
        else:
            col1.metric("💓 最新心跳序号", "无")
            col2.metric("⏱️ 最新心跳时间", "无")

        # 掉线报警状态
        _, status_msg = heartbeat_status()
        if "超时" in status_msg:
            st.error(status_msg)
        elif "等待" in status_msg:
            st.info(status_msg)
        else:
            st.success(status_msg)

        # 折线图 (心跳序号变化趋势)
        if len(st.session_state.heartbeat_list) >= 2:
            df = pd.DataFrame(st.session_state.heartbeat_list, columns=["序号", "时间", "dt"])
            fig = px.line(df, x="时间", y="序号", title="📈 心跳序号变化趋势", markers=True,
                          labels={"序号": "心跳序号", "时间": "接收时间"})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        elif len(st.session_state.heartbeat_list) == 1:
            st.info("📊 已收到 1 个心跳包，继续接收后将显示趋势图")
        else:
            st.info("📊 等待无人机心跳数据...")

        # 数据表格 (最近10条)
        if st.session_state.heartbeat_list:
            df_table = pd.DataFrame(st.session_state.heartbeat_list[-10:], columns=["序号", "时间", "dt"])
            st.dataframe(df_table.drop(columns=["dt"]), use_container_width=True)
        else:
            st.info("暂无心跳记录")

        # 自动刷新 (每秒)
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
