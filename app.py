# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
import json
import os
from datetime import datetime
from streamlit_folium import st_folium
import folium
from folium import plugins
from shapely.geometry import Polygon, Point, LineString

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 智能航线规划", layout="wide")

# ==================== 坐标系转换 ====================
def wgs84_to_gcj02(lng, lat):
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
    wgs_lng, wgs_lat = wgs84_to_gcj02(lng, lat)
    return 2*lng - wgs_lng, 2*lat - wgs_lat

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

# ==================== 障碍物数据结构与持久化 ====================
CONFIG_FILE = "obstacle_config.json"

def normalize_obstacle(obs):
    if isinstance(obs, list):
        return {"polygon": obs, "height": 10.0}
    if isinstance(obs, dict):
        if "polygon" not in obs:
            if "coordinates" in obs:
                return {"polygon": obs["coordinates"], "height": float(obs.get("height", 10.0))}
            else:
                return {"polygon": [], "height": 10.0}
        return {"polygon": obs["polygon"], "height": float(obs.get("height", 10.0))}
    return {"polygon": [], "height": 10.0}

def load_obstacles():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [normalize_obstacle(obs) for obs in data]
                else:
                    return []
        except:
            return []
    return []

def save_obstacles(obstacles):
    to_save = []
    for obs in obstacles:
        if isinstance(obs, dict) and "polygon" in obs and obs["polygon"]:
            to_save.append({"polygon": obs["polygon"], "height": float(obs.get("height", 10.0))})
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)

# ==================== 航线规划算法（修复：飞行高度 ≤ 障碍物高度时强制绕行）====================
def line_intersects_polygon(A, B, polygon):
    if not polygon or len(polygon) < 3:
        return False
    line = LineString([A, B])
    poly = Polygon(polygon)
    return line.intersects(poly)

def get_offset_points(A, B, offset_meters, direction='left'):
    dx = B[0] - A[0]
    dy = B[1] - A[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return A, B
    ux = dx / length
    uy = dy / length
    perp_x = -uy if direction == 'left' else uy
    perp_y = ux if direction == 'left' else -ux
    lat_rad = math.radians((A[1] + B[1]) / 2)
    meter_per_deg_lon = 111320 * math.cos(lat_rad)
    meter_per_deg_lat = 110540
    offset_lon = offset_meters / meter_per_deg_lon * perp_x
    offset_lat = offset_meters / meter_per_deg_lat * perp_y
    A_new = (A[0] + offset_lon, A[1] + offset_lat)
    B_new = (B[0] + offset_lon, B[1] + offset_lat)
    return A_new, B_new

def compute_avoidance_path(A, B, obstacles, flight_height, safe_radius, strategy):
    path = [A]
    current = A
    # 对每个障碍物迭代处理（简化版：按顺序处理，重新扫描）
    for _ in range(20):
        any_intersection = False
        for obs in obstacles:
            poly = obs.get("polygon", [])
            if not poly or len(poly) < 3:
                continue
            height = obs.get("height", 10.0)
            if line_intersects_polygon(current, B, poly):
                any_intersection = True
                # 决策：若飞行高度 > 障碍物高度，则飞跃（不做绕行）
                if flight_height > height:
                    continue
                # 否则必须绕行
                if strategy == "向左绕行":
                    offset_A, offset_B = get_offset_points(current, B, safe_radius * 2.5, 'left')
                elif strategy == "向右绕行":
                    offset_A, offset_B = get_offset_points(current, B, safe_radius * 2.5, 'right')
                else:  # 最佳航线
                    left_A, left_B = get_offset_points(current, B, safe_radius * 2.5, 'left')
                    right_A, right_B = get_offset_points(current, B, safe_radius * 2.5, 'right')
                    left_ok = True
                    right_ok = True
                    for o in obstacles:
                        p = o.get("polygon", [])
                        if not p:
                            continue
                        if line_intersects_polygon(left_A, left_B, p):
                            left_ok = False
                        if line_intersects_polygon(right_A, right_B, p):
                            right_ok = False
                    if left_ok and right_ok:
                        left_len = math.hypot(left_A[0]-left_B[0], left_A[1]-left_B[1])
                        right_len = math.hypot(right_A[0]-right_B[0], right_A[1]-right_B[1])
                        offset_A, offset_B = (left_A, left_B) if left_len < right_len else (right_A, right_B)
                    elif left_ok:
                        offset_A, offset_B = left_A, left_B
                    elif right_ok:
                        offset_A, offset_B = right_A, right_B
                    else:
                        offset_A, offset_B = get_offset_points(current, B, safe_radius * 4, 'left')
                path.append(offset_A)
                path.append(offset_B)
                current = offset_B
                break  # 重新扫描新的当前点
        if not any_intersection:
            path.append(B)
            break
    else:
        path.append(B)
    # 简化路径
    simplified = [path[0]]
    for i in range(1, len(path)-1):
        p1 = simplified[-1]
        p2 = path[i]
        p3 = path[i+1]
        if abs((p2[0]-p1[0])*(p3[1]-p2[1]) - (p2[1]-p1[1])*(p3[0]-p2[0])) > 1e-6:
            simplified.append(p2)
    simplified.append(path[-1])
    return simplified

# ==================== 创建地图 ====================
def create_map(center_lat, center_lng, obstacles, A_wgs, B_wgs, flight_path, safe_radius):
    m = folium.Map(location=[center_lat, center_lng], zoom_start=16, control_scale=True)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri',
        name='卫星影像'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='街道图').add_to(m)
    folium.LayerControl().add_to(m)
    for obs in obstacles:
        coords = obs.get("polygon", [])
        if coords and len(coords) >= 3:
            height = obs.get("height", 10.0)
            folium.Polygon(
                locations=[[lat, lng] for lng, lat in coords],
                color='orange',
                weight=3,
                fillOpacity=0.3,
                popup=f'障碍物高度: {height} m'
            ).add_to(m)
    folium.Marker(A_wgs, popup="起点 A", icon=folium.Icon(color='green', icon='play', prefix='fa')).add_to(m)
    folium.Marker(B_wgs, popup="终点 B", icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa')).add_to(m)
    if flight_path and len(flight_path) > 1:
        path_latlng = [(lat, lng) for lng, lat in flight_path]
        folium.PolyLine(path_latlng, color='cyan', weight=4, opacity=0.8, tooltip='规划航线').add_to(m)
    draw = plugins.Draw(
        draw_options={'polygon': True, 'polyline': False, 'rectangle': False, 'circle': False, 'marker': False},
        edit_options={'edit': True, 'remove': True}
    )
    draw.add_to(m)
    return m

# ==================== 主应用 ====================
def main():
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (智能避障)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    
    st.sidebar.subheader("坐标系设置")
    coord_sys = st.sidebar.radio("输入坐标系", ["GCJ-02 (高德/百度)", "WGS-84"], index=0)
    
    st.sidebar.subheader("系统状态")
    a_set = ("A_lat_gcj" in st.session_state and "A_lng_gcj" in st.session_state)
    b_set = ("B_lat_gcj" in st.session_state and "B_lng_gcj" in st.session_state)
    st.sidebar.write(f"{'✅' if a_set else '❌'} A点已设")
    st.sidebar.write(f"{'✅' if b_set else '❌'} B点已设")
    st.sidebar.markdown("---")
    st.sidebar.info("🗺️ 卫星图源: Esri | 飞行高度 ≤ 障碍物高度时强制绕行")
    
    # 初始化坐标 (GCJ-02)
    if "A_lat_gcj" not in st.session_state:
        st.session_state.A_lat_gcj = 32.2323
        st.session_state.A_lng_gcj = 118.7490
    if "B_lat_gcj" not in st.session_state:
        st.session_state.B_lat_gcj = 32.2344
        st.session_state.B_lng_gcj = 118.7490
    if "flight_height" not in st.session_state:
        st.session_state.flight_height = 30.0
    if "safe_radius" not in st.session_state:
        st.session_state.safe_radius = 5.0
    if "bypass_strategy" not in st.session_state:
        st.session_state.bypass_strategy = "最佳航线"
    
    if "obstacles" not in st.session_state:
        st.session_state.obstacles = load_obstacles()
    else:
        st.session_state.obstacles = [normalize_obstacle(obs) for obs in st.session_state.obstacles]
    
    if page == "🗺️ 航线规划 (智能避障)":
        left_col, right_col = st.columns([7, 3])
        with right_col:
            st.markdown("### 🎮 控制面板")
            st.markdown(f"**当前坐标系: {coord_sys}**")
            
            # 起点 A
            st.markdown("#### 🚁 起点 A")
            if coord_sys == "GCJ-02 (高德/百度)":
                a_lat = st.number_input("纬度 (A)", value=float(st.session_state.A_lat_gcj), format="%.6f", key="a_lat")
                a_lng = st.number_input("经度 (A)", value=float(st.session_state.A_lng_gcj), format="%.6f", key="a_lng")
            else:
                wgs_lng, wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
                a_lat = st.number_input("纬度 (A)", value=float(wgs_lat), format="%.6f", key="a_lat_wgs")
                a_lng = st.number_input("经度 (A)", value=float(wgs_lng), format="%.6f", key="a_lng_wgs")
            if st.button("✅ 设置 A 点"):
                if coord_sys == "GCJ-02 (高德/百度)":
                    st.session_state.A_lat_gcj = a_lat
                    st.session_state.A_lng_gcj = a_lng
                else:
                    gcj_lng, gcj_lat = wgs84_to_gcj02(a_lng, a_lat)
                    st.session_state.A_lat_gcj = gcj_lat
                    st.session_state.A_lng_gcj = gcj_lng
                st.success("A点已更新")
                st.rerun()
            
            # 终点 B
            st.markdown("#### 📍 终点 B")
            if coord_sys == "GCJ-02 (高德/百度)":
                b_lat = st.number_input("纬度 (B)", value=float(st.session_state.B_lat_gcj), format="%.6f", key="b_lat")
                b_lng = st.number_input("经度 (B)", value=float(st.session_state.B_lng_gcj), format="%.6f", key="b_lng")
            else:
                wgs_lng, wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
                b_lat = st.number_input("纬度 (B)", value=float(wgs_lat), format="%.6f", key="b_lat_wgs")
                b_lng = st.number_input("经度 (B)", value=float(wgs_lng), format="%.6f", key="b_lng_wgs")
            if st.button("✅ 设置 B 点"):
                if coord_sys == "GCJ-02 (高德/百度)":
                    st.session_state.B_lat_gcj = b_lat
                    st.session_state.B_lng_gcj = b_lng
                else:
                    gcj_lng, gcj_lat = wgs84_to_gcj02(b_lng, b_lat)
                    st.session_state.B_lat_gcj = gcj_lat
                    st.session_state.B_lng_gcj = gcj_lng
                st.success("B点已更新")
                st.rerun()
            
            # 飞行参数
            st.markdown("#### ✈️ 飞行参数")
            flight_h = st.number_input("飞行高度 (m)", value=float(st.session_state.flight_height), step=5.0, min_value=0.0)
            st.session_state.flight_height = flight_h
            safe_r = st.number_input("安全半径 (m)", value=float(st.session_state.safe_radius), step=1.0, min_value=0.0)
            st.session_state.safe_radius = safe_r
            strategy = st.selectbox("绕行策略", ["向左绕行", "向右绕行", "最佳航线"], index=["向左绕行","向右绕行","最佳航线"].index(st.session_state.bypass_strategy))
            st.session_state.bypass_strategy = strategy
            
            st.markdown("---")
            st.markdown("#### 🧱 障碍物管理")
            for i, obs in enumerate(st.session_state.obstacles):
                poly = obs.get("polygon", [])
                if not poly:
                    continue
                with st.expander(f"障碍物 {i+1} (高度 {obs.get('height',10):.1f} m)", expanded=False):
                    new_height = st.number_input(f"高度 (米)", value=float(obs.get("height", 10.0)), step=1.0, key=f"height_edit_{i}")
                    if new_height != obs.get("height", 10.0):
                        obs["height"] = new_height
                        save_obstacles(st.session_state.obstacles)
                        st.success("高度已更新")
                    if st.button(f"🗑️ 删除此障碍物", key=f"del_btn_{i}"):
                        st.session_state.obstacles.pop(i)
                        save_obstacles(st.session_state.obstacles)
                        st.rerun()
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("💾 保存所有到文件"):
                    save_obstacles(st.session_state.obstacles)
                    st.success("已保存")
            with col_btn2:
                if st.button("📂 从文件加载"):
                    st.session_state.obstacles = load_obstacles()
                    st.success("已加载")
                    st.rerun()
            with col_btn3:
                if st.button("🗑️ 清除所有障碍物"):
                    st.session_state.obstacles = []
                    save_obstacles([])
                    st.success("已清除")
                    st.rerun()
            
            obstacle_json_str = json.dumps(st.session_state.obstacles, ensure_ascii=False, indent=2)
            st.download_button("📥 下载 obstacle_config.json", data=obstacle_json_str, file_name="obstacle_config.json", mime="application/json")
            st.caption(f"当前障碍物数量: {len(st.session_state.obstacles)}")
        
        with left_col:
            st.markdown("### 🗺️ 卫星实况地图 (可绘制多边形)")
            A_wgs_lng, A_wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
            B_wgs_lng, B_wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
            center_lat = (A_wgs_lat + B_wgs_lat) / 2
            center_lng = (A_wgs_lng + B_wgs_lng) / 2
            
            A_point = (A_wgs_lng, A_wgs_lat)
            B_point = (B_wgs_lng, B_wgs_lat)
            path = compute_avoidance_path(A_point, B_point, st.session_state.obstacles, st.session_state.flight_height, st.session_state.safe_radius, st.session_state.bypass_strategy)
            
            folium_map = create_map(center_lat, center_lng, st.session_state.obstacles, (A_wgs_lat, A_wgs_lng), (B_wgs_lat, B_wgs_lng), path, st.session_state.safe_radius)
            output = st_folium(folium_map, width=800, height=600, returned_objects=["last_active_drawing"], key="folium_map")
            
            if output and output.get("last_active_drawing"):
                drawing = output["last_active_drawing"]
                if drawing and drawing.get("geometry") and drawing["geometry"]["type"] == "Polygon":
                    coords = drawing["geometry"]["coordinates"][0]
                    new_polygon = [[p[0], p[1]] for p in coords]
                    exists = any(obs.get("polygon") == new_polygon for obs in st.session_state.obstacles)
                    if not exists:
                        new_obs = {"polygon": new_polygon, "height": 10.0}
                        st.session_state.obstacles.append(new_obs)
                        save_obstacles(st.session_state.obstacles)
                        st.success("✅ 已添加新障碍物（默认高度10米）")
                        st.rerun()
    
    elif page == "📡 飞行监控 (心跳监测)":
        st.header("📡 无人机心跳监测 · 实时数据")
        init_heartbeat()
        enable = st.sidebar.checkbox("🚁 允许无人机发送心跳包", value=True, key="hb_enable")
        update_heartbeat(enable)
        
        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("💓 最新心跳序号", latest[0])
            col2.metric("⏱️ 最新心跳时间", latest[1])
        else:
            col1.metric("💓 最新心跳序号", "无")
            col2.metric("⏱️ 最新心跳时间", "无")
        
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
            st.info("已收到1个心跳，继续接收后将显示趋势图")
        else:
            st.info("等待心跳数据...")
        
        if st.session_state.heartbeat_list:
            df_tab = pd.DataFrame(st.session_state.heartbeat_list[-10:], columns=["序号", "时间", "dt"])
            st.dataframe(df_tab.drop(columns=["dt"]), use_container_width=True)
        else:
            st.info("暂无心跳记录")
        
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
