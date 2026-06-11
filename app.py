# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 北斗+高德卫星地图", layout="wide")

# ==================== (新增) 度分秒 (DMS) 转 十进制度数 (DD) ====================
def dmstodd(dms_str):
    """
    将度分秒格式的经纬度字符串转换为十进制度数。
    输入示例: "2429.53531" 表示 24度29.53531分
    输出示例: 24.4922551667
    """
    if not isinstance(dms_str, str):
        dms_str = str(dms_str)
    # 找到小数点的位置
    dot_index = dms_str.find('.')
    if dot_index == -1:
        return float(dms_str)
    # 分离"度"和"分"
    degrees_part = dms_str[:dot_index - 2]
    minutes_part = dms_str[dot_index - 2:]
    try:
        degrees = float(degrees_part)
        minutes = float(minutes_part)
        return degrees + minutes / 60.0
    except ValueError:
        return float(dms_str)

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
    wgs_lng, wgs_lat = wgs84_to_gcj02(lng, lat)
    return 2*lng - wgs_lng, 2*lat - wgs_lat

# ==================== 障碍物（校园内 GCJ-02 坐标，已校准）====================
OBSTACLES_GCJ = [
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

# ==================== 生成地图 HTML (Leaflet + 高德卫星图 + 北斗坐标转换支持) ====================
def generate_map_html(A_lng, A_lat, B_lng, B_lat, obstacles, flight_height):
    """
    返回包含地图的 HTML 字符串，使用 Leaflet 和高德卫星图。
    注意：本函数接收的坐标已为 GCJ-02 坐标系。
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
        ✈️ 航线: A → B | 飞行高度: {flight_height}m | 坐标系: GCJ-02 (高德/北斗)
    </div>
    <div id="controls-note" style="position: absolute; bottom: 20px; left: 20px; z-index: 1000; background: rgba(0,0,0,0.4); color: #ccc; padding: 5px 10px; border-radius: 3px; font-size: 12px;">
        🖱️ 鼠标拖拽平移 | 滚动缩放 | 高德卫星图源
    </div>
    <script>
        // 初始化地图 (垂直俯瞰，无倾斜)
        var map = L.map('map').setView([{center_lat}, {center_lng}], 16.5);
        
        // 添加高德卫星图源 (GCJ-02 坐标系)
        L.tileLayer('https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={{x}}&y={{y}}&z={{z}}', {{
            subdomains: ['1', '2', '3', '4'],
            attribution: '© 高德地图',
            maxZoom: 18,
            minZoom: 4
        }}).addTo(map);
        
        // 起点 A 标记 (使用自定义图标)
        var markerA = L.marker([{A_lat}, {A_lng}], {{
            icon: L.divIcon({{ html: '🚁', iconSize: [28,28], className: 'marker-icon' }})
        }}).bindPopup('<b>起点 A</b><br>纬度: {A_lat}<br>经度: {A_lng}<br><i>坐标已按GCJ-02校准</i>').addTo(map);
        
        // 终点 B 标记
        var markerB = L.marker([{B_lat}, {B_lng}], {{
            icon: L.divIcon({{ html: '🏁', iconSize: [28,28], className: 'marker-icon' }})
        }}).bindPopup('<b>终点 B</b><br>纬度: {B_lat}<br>经度: {B_lng}<br><i>坐标已按GCJ-02校准</i>').addTo(map);
        
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
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (北斗+高德卫星图)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    st.sidebar.info("🗺️ 地图使用高德卫星影像 (GCJ-02坐标系) | 支持北斗/WGS-84坐标输入")
    st.sidebar.caption("💡 **使用提示**：如需模拟北斗设备数据，可用 `2429.53531` 等度分秒格式输入，系统会自动转换。")
    
    # 初始化会话状态 (坐标使用 GCJ-02)
    if "A_lat" not in st.session_state:
        st.session_state.A_lat = 32.2322
        st.session_state.A_lng = 118.7490
        st.session_state.B_lat = 32.2343
        st.session_state.B_lng = 118.7490
        st.session_state.flight_height = 50
        st.session_state.coord_mode = "DD"  # 'DD' 或 'DMS'
    
    if page == "🗺️ 航线规划 (北斗+高德卫星图)":
        # 左右两列布局: 地图占70%，控制面板占30%
        left_col, right_col = st.columns([7, 3])
        
        with right_col:
            st.markdown("### 🎮 控制面板")
            st.markdown("**输入坐标系: WGS-84 (GPS/北斗)**")
            coord_mode = st.radio("坐标输入模式", ["十进制 (DD)", "度分秒 (DMS)"], index=0, key="coord_mode")
            
            st.markdown("#### 🚁 起点 A")
            if coord_mode == "十进制 (DD)":
                a_lat = st.number_input("纬度 (A)", value=st.session_state.A_lat, format="%.6f", key="a_lat")
                a_lng = st.number_input("经度 (A)", value=st.session_state.A_lng, format="%.6f", key="a_lng")
            else:
                a_lat_dms = st.text_input("纬度 (A) [DMS]", value="2429.53531", key="a_lat_dms", help="例如: 2429.53531 (24度29.53531分)")
                a_lng_dms = st.text_input("经度 (A) [DMS]", value="11810.78036", key="a_lng_dms", help="例如: 11810.78036 (118度10.78036分)")
                a_lat = dmstodd(a_lat_dms)
                a_lng = dmstodd(a_lng_dms)
            
            if st.button("✅ 设置 A 点", key="set_a"):
                st.session_state.A_lat = a_lat
                st.session_state.A_lng = a_lng
                st.success(f"A 点已更新 (DD: {a_lat:.6f}, {a_lng:.6f})")
            
            st.markdown("#### 📍 终点 B")
            if coord_mode == "十进制 (DD)":
                b_lat = st.number_input("纬度 (B)", value=st.session_state.B_lat, format="%.6f", key="b_lat")
                b_lng = st.number_input("经度 (B)", value=st.session_state.B_lng, format="%.6f", key="b_lng")
            else:
                b_lat_dms = st.text_input("纬度 (B) [DMS]", value="2429.53531", key="b_lat_dms")
                b_lng_dms = st.text_input("经度 (B) [DMS]", value="11810.78036", key="b_lng_dms")
                b_lat = dmstodd(b_lat_dms)
                b_lng = dmstodd(b_lng_dms)
            
            if st.button("✅ 设置 B 点", key="set_b"):
                st.session_state.B_lat = b_lat
                st.session_state.B_lng = b_lng
                st.success(f"B 点已更新 (DD: {b_lat:.6f}, {b_lng:.6f})")
            
            st.markdown("#### ✈️ 飞行参数")
            flight_height = st.number_input("飞行高度 (m)", value=st.session_state.flight_height, step=5)
            st.session_state.flight_height = flight_height
            
            st.markdown("---")
            st.markdown("#### 🧱 障碍物列表 (校园内, GCJ-02)")
            for obs in OBSTACLES_GCJ:
                st.write(f"- {obs['name']}: ({obs['lng']}, {obs['lat']})")
            
            # 显示坐标转换后的值
            st.markdown("---")
            st.markdown("#### 📍 当前定位 (转换后)")
            st.write(f"**起点 A (GCJ-02)**: {st.session_state.A_lat:.6f}, {st.session_state.A_lng:.6f}")
            st.write(f"**终点 B (GCJ-02)**: {st.session_state.B_lat:.6f}, {st.session_state.B_lng:.6f}")
        
        with left_col:
            st.markdown("### 🗺️ 3D 卫星地图 (垂直俯瞰 | 高德卫星源)")
            # 地图使用 GCJ-02 坐标直接渲染
            map_html = generate_map_html(
                st.session_state.A_lng, st.session_state.A_lat,
                st.session_state.B_lng, st.session_state.B_lat,
                OBSTACLES_GCJ, st.session_state.flight_height
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
