# app.py - 最终版（沿原直线，仅在障碍物处绕行并回正）
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
from shapely.ops import nearest_points

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

# ==================== 几何辅助函数 ====================
def line_intersects_polygon(A, B, polygon):
    if not polygon or len(polygon) < 3:
        return False
    line = LineString([A, B])
    poly = Polygon(polygon)
    return line.intersects(poly)

def get_line_polygon_intersection_points(A, B, polygon):
    """返回线段与多边形的两个交点（进入点和离开点），按从A到B的顺序"""
    line = LineString([A, B])
    poly = Polygon(polygon)
    if not line.intersects(poly):
        return None, None
    intersection = line.intersection(poly)
    if intersection.is_empty:
        return None, None
    points = []
    if intersection.geom_type == 'Point':
        points = [(intersection.x, intersection.y)]
    elif intersection.geom_type == 'MultiPoint':
        points = [(pt.x, pt.y) for pt in intersection.geoms]
    elif intersection.geom_type == 'LineString':
        coords = list(intersection.coords)
        points = [(c[0], c[1]) for c in coords]
    elif intersection.geom_type == 'MultiLineString':
        # 取所有线段的端点
        for geom in intersection.geoms:
            coords = list(geom.coords)
            points.extend([(c[0], c[1]) for c in coords])
    else:
        # 其他情况，取几何体的边界点
        try:
            coords = list(intersection.exterior.coords) if intersection.geom_type == 'Polygon' else []
            points = [(c[0], c[1]) for c in coords]
        except:
            pass
    if not points:
        return None, None
    # 按距离A排序
    def dist(p):
        return math.hypot(p[0]-A[0], p[1]-A[1])
    points.sort(key=dist)
    # 去重（近似）
    unique = []
    for p in points:
        if not unique or distance_meters(p, unique[-1]) > 1e-3:
            unique.append(p)
    if len(unique) >= 2:
        return unique[0], unique[-1]
    elif len(unique) == 1:
        return unique[0], None
    else:
        return None, None

def distance_meters(p1, p2):
    lat_rad = math.radians((p1[1] + p2[1]) / 2)
    meter_per_deg_lon = 111320 * math.cos(lat_rad)
    meter_per_deg_lat = 110540
    dx = (p2[0] - p1[0]) * meter_per_deg_lon
    dy = (p2[1] - p1[1]) * meter_per_deg_lat
    return math.hypot(dx, dy)

def interpolate_point_on_line(A, B, distance_from_A_meters):
    total_dist = distance_meters(A, B)
    if total_dist < 1e-6:
        return A
    t = distance_from_A_meters / total_dist
    t = max(0.0, min(1.0, t))
    return (A[0] + t * (B[0] - A[0]), A[1] + t * (B[1] - A[1]))

def get_offset_points_with_start(start_point, B, offset_meters, direction='left'):
    dx = B[0] - start_point[0]
    dy = B[1] - start_point[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return start_point, B
    ux = dx / length
    uy = dy / length
    perp_x = -uy
    perp_y = ux
    if direction == 'right':
        perp_x = -perp_x
        perp_y = -perp_y
    lat_rad = math.radians((start_point[1] + B[1]) / 2)
    meter_per_deg_lon = 111320 * math.cos(lat_rad)
    meter_per_deg_lat = 110540
    offset_lon = offset_meters / meter_per_deg_lon * perp_x
    offset_lat = offset_meters / meter_per_deg_lat * perp_y
    new_start = (start_point[0] + offset_lon, start_point[1] + offset_lat)
    new_end = (B[0] + offset_lon, B[1] + offset_lat)
    return new_start, new_end

def get_buffer_polygon(polygon, safe_radius, ref_point):
    if not polygon or len(polygon) < 3:
        return None
    center_lng, center_lat = ref_point
    meter_per_deg_lon = 111320 * math.cos(math.radians(center_lat))
    meter_per_deg_lat = 110540
    local_points = []
    for p in polygon:
        dx = (p[0] - center_lng) * meter_per_deg_lon
        dy = (p[1] - center_lat) * meter_per_deg_lat
        local_points.append((dx, dy))
    local_poly = Polygon(local_points)
    buffered = local_poly.buffer(safe_radius)
    buffered_coords = []
    for pt in buffered.exterior.coords:
        lng = center_lng + pt[0] / meter_per_deg_lon
        lat = center_lat + pt[1] / meter_per_deg_lat
        buffered_coords.append((lng, lat))
    return buffered_coords

def enforce_safe_distance(path, obstacles, safe_radius):
    if not obstacles or not path:
        return path
    poly_list = []
    for obs in obstacles:
        poly = obs.get("polygon", [])
        if poly and len(poly) >= 3:
            poly_list.append(Polygon(poly))
    if not poly_list:
        return path
    for _ in range(3):
        new_path = []
        for pt in path:
            point = Point(pt[0], pt[1])
            min_dist = float('inf')
            nearest_poly = None
            for poly in poly_list:
                d = point.distance(poly)
                if d < min_dist:
                    min_dist = d
                    nearest_poly = poly
            if min_dist < safe_radius and nearest_poly is not None:
                nearest_pt = nearest_points(point, nearest_poly)[1]
                dx = pt[0] - nearest_pt.x
                dy = pt[1] - nearest_pt.y
                length = math.hypot(dx, dy)
                if length > 1e-8:
                    lat_rad = math.radians(pt[1])
                    meter_per_deg_lon = 111320 * math.cos(lat_rad)
                    meter_per_deg_lat = 110540
                    offset_lon = (safe_radius - min_dist + 0.5) / meter_per_deg_lon * (dx / length)
                    offset_lat = (safe_radius - min_dist + 0.5) / meter_per_deg_lat * (dy / length)
                    new_pt = (pt[0] + offset_lon, pt[1] + offset_lat)
                    new_path.append(new_pt)
                else:
                    new_path.append(pt)
            else:
                new_path.append(pt)
        path = new_path
    return path

# ==================== 核心航线规划（沿原直线，仅在障碍物处绕行并回正）====================
def compute_avoidance_path(A, B, obstacles, flight_height, safe_radius, strategy):
    if not obstacles:
        return [A, B]
    # 预计算原始直线
    raw_path = [A, B]
    # 检测所有与直线相交且需要绕行的障碍物，按距离A排序
    hit_obstacles = []
    for obs in obstacles:
        poly = obs.get("polygon", [])
        if not poly or len(poly) < 3:
            continue
        height = obs.get("height", 10.0)
        if flight_height <= height and line_intersects_polygon(A, B, poly):
            # 获取进入点和离开点
            entry, exit_pt = get_line_polygon_intersection_points(A, B, poly)
            if entry is not None:
                hit_obstacles.append({
                    'obs': obs,
                    'poly': poly,
                    'entry': entry,
                    'exit': exit_pt,
                    'dist_entry': distance_meters(A, entry)
                })
    # 按进入点排序
    hit_obstacles.sort(key=lambda x: x['dist_entry'])
    # 构建路径：逐段拼接直线和绕行段
    path = [A]
    current = A
    for idx, hit in enumerate(hit_obstacles):
        entry = hit['entry']
        exit_pt = hit['exit']
        # 从 current 直线前进到 entry 前 safe_radius 处（绕行起点）
        dist_to_entry = distance_meters(current, entry)
        if dist_to_entry > safe_radius:
            start_offset = max(0.0, dist_to_entry - safe_radius)
            start_point = interpolate_point_on_line(current, B, start_offset)
        else:
            start_point = current
        # 如果起点与当前点不同，添加直线段
        if distance_meters(current, start_point) > 1e-6:
            path.append(start_point)
        # 生成绕行段：从 start_point 到 exit_pt 后 safe_radius 处的点（绕行终点）
        # 先计算 exit_pt 后 safe_radius 处的点
        dist_exit_to_B = distance_meters(exit_pt, B)
        if dist_exit_to_B > safe_radius:
            end_offset = min(dist_exit_to_B, safe_radius)
            end_point = interpolate_point_on_line(exit_pt, B, end_offset)
        else:
            end_point = B
        # 在 start_point 到 end_point 之间生成偏移路径，偏移距离从 safe_radius*3 开始逐步增加
        offset_m = safe_radius * 3
        success = False
        best_start, best_end = None, None
        for attempt in range(40):
            if strategy == "向左绕行":
                dirs = ['left']
            elif strategy == "向右绕行":
                dirs = ['right']
            else:
                dirs = ['left', 'right']
            for d in dirs:
                # 生成偏移线段，从 start_point 到 end_point
                off_start, off_end = get_offset_points_with_start(start_point, end_point, offset_m, d)
                # 检查偏移线段是否与任何障碍物（原始多边形）相交（用缓冲区检测更好）
                # 但这里用原始多边形检测，因为偏移后的路径需要避开障碍物本身
                intersect = False
                for obs2 in obstacles:
                    p2 = obs2.get("polygon", [])
                    if p2 and len(p2) >= 3:
                        if line_intersects_polygon(off_start, off_end, p2):
                            intersect = True
                            break
                if not intersect:
                    # 进一步检查与障碍物缓冲区的距离（确保安全距离）
                    safe = True
                    for obs2 in obstacles:
                        p2 = obs2.get("polygon", [])
                        if p2 and len(p2) >= 3:
                            # 检查 off_start 和 off_end 到多边形距离
                            poly_shapely = Polygon(p2)
                            if Point(off_start[0], off_start[1]).distance(poly_shapely) < safe_radius:
                                safe = False
                                break
                            if Point(off_end[0], off_end[1]).distance(poly_shapely) < safe_radius:
                                safe = False
                                break
                    if safe:
                        best_start, best_end = off_start, off_end
                        success = True
                        break
            if success:
                break
            offset_m += safe_radius
        if success:
            path.append(best_start)
            # 从 best_end 到终点 B 可能会经过其他障碍物，但我们将继续循环处理
            # 将 current 设为 best_end，继续处理后续障碍物（但后续障碍物已经在 hit_obstacles 中，我们将跳过已处理的）
            current = best_end
        else:
            # 无法绕行，直接跳到 B
            path.append(B)
            break
        # 如果当前绕行段的终点已经接近 B，结束
        if distance_meters(current, B) < 1e-6:
            break
    # 如果最后没有到达 B，添加直线段
    if distance_meters(current, B) > 1e-6:
        path.append(B)
    # 简化路径
    simplified = [path[0]]
    for i in range(1, len(path)-1):
        p1 = simplified[-1]
        p2 = path[i]
        p3 = path[i+1]
        if abs((p2[0]-p1[0])*(p3[1]-p2[1]) - (p2[1]-p1[1])*(p3[0]-p2[0])) > 1e-8:
            simplified.append(p2)
    simplified.append(path[-1])
    # 后处理：确保每个点距离障碍物至少 safe_radius
    final_path = enforce_safe_distance(simplified, obstacles, safe_radius)
    return final_path

# ==================== 创建地图 ====================
def create_map(center_lat, center_lng, obstacles, A_wgs, B_wgs, flight_path, safe_radius):
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=15,
        control_scale=True,
        tiles=None
    )
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri',
        name='卫星影像'
    ).add_to(m)
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='街道图'
    ).add_to(m)
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
        draw_options={
            'polygon': True,
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False
        }
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
    st.sidebar.info("🗺️ 卫星图源: Esri | 沿原直线，障碍物处绕行并回正")
    
    # 初始化默认坐标 (GCJ-02)
    if "A_lat_gcj" not in st.session_state:
        st.session_state.A_lat_gcj = 32.230500
        st.session_state.A_lng_gcj = 118.748500
    if "B_lat_gcj" not in st.session_state:
        st.session_state.B_lat_gcj = 32.238000
        st.session_state.B_lng_gcj = 118.754000
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
            st.markdown("### 🗺️ 卫星地图 (可绘制多边形圈选障碍物)")
            st.caption("💡 如卫星图未显示，请点击地图右上角图层按钮切换至\"街道图\"")
            A_wgs_lng, A_wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
            B_wgs_lng, B_wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
            center_lat = (A_wgs_lat + B_wgs_lat) / 2
            center_lng = (A_wgs_lng + B_wgs_lng) / 2
            
            A_point = (A_wgs_lng, A_wgs_lat)
            B_point = (B_wgs_lng, B_wgs_lat)
            path = compute_avoidance_path(A_point, B_point, st.session_state.obstacles, st.session_state.flight_height, st.session_state.safe_radius, st.session_state.bypass_strategy)
            
            folium_map = create_map(center_lat, center_lng, st.session_state.obstacles, (A_wgs_lat, A_wgs_lng), (B_wgs_lat, B_wgs_lng), path, st.session_state.safe_radius)
            output = st_folium(folium_map, width=800, height=600, key="unique_map_key")
            
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
