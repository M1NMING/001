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

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 多边形圈选 + 心跳监测", layout="wide")

# ==================== 坐标系转换 (GCJ-02 ↔ WGS-84) ====================
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

# ==================== 障碍物持久化配置 ====================
CONFIG_FILE = "obstacle_config.json"

def load_obstacles():
    """从文件加载障碍物GeoJSON"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"type": "FeatureCollection", "features": []}

def save_obstacles(geojson):
    """保存障碍物GeoJSON到文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

# ==================== 创建带绘制工具的地图 ====================
def create_map(center_lat, center_lng, zoom_start=16):
    """创建Folium地图，添加多边形绘制工具"""
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_start, control_scale=True)
    # 添加卫星图源（Esri 卫星）
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri',
        name='卫星影像',
        overlay=False,
        control=True
    ).add_to(m)
    # 添加一个普通街道图作为备选
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='街道图',
        overlay=False,
        control=True
    ).add_to(m)
    # 添加图层控制
    folium.LayerControl().add_to(m)
    # 添加绘制控件（允许绘制多边形）
    draw = plugins.Draw(
        draw_options={
            'polygon': True,
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False
        },
        edit_options={'edit': True, 'remove': True}
    )
    draw.add_to(m)
    return m

# ==================== 主应用 ====================
def main():
    # 侧边栏导航
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (多边形圈选)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    
    # 坐标系设置
    st.sidebar.subheader("坐标系设置")
    coord_sys = st.sidebar.radio("输入坐标系", ["GCJ-02 (高德/百度)", "WGS-84"], index=0)
    
    # 系统状态
    st.sidebar.subheader("系统状态")
    a_set = ("A_lat_gcj" in st.session_state and "A_lng_gcj" in st.session_state)
    b_set = ("B_lat_gcj" in st.session_state and "B_lng_gcj" in st.session_state)
    st.sidebar.write(f"{'✅' if a_set else '❌'} A点已设")
    st.sidebar.write(f"{'✅' if b_set else '❌'} B点已设")
    
    st.sidebar.markdown("---")
    st.sidebar.info("🗺️ 卫星图源: Esri World Imagery\n✏️ 在地图上绘制多边形圈选障碍物\n💾 支持保存/加载配置")
    
    # 初始化A/B点坐标 (GCJ-02)
    if "A_lat_gcj" not in st.session_state:
        st.session_state.A_lat_gcj = 32.2323
        st.session_state.A_lng_gcj = 118.7490
    if "B_lat_gcj" not in st.session_state:
        st.session_state.B_lat_gcj = 32.2344
        st.session_state.B_lng_gcj = 118.7490
    if "flight_height" not in st.session_state:
        st.session_state.flight_height = 10
    
    # 加载已有障碍物配置
    if "obstacle_geojson" not in st.session_state:
        st.session_state.obstacle_geojson = load_obstacles()
    
    if page == "🗺️ 航线规划 (多边形圈选)":
        left_col, right_col = st.columns([7, 3])
        
        with right_col:
            st.markdown("### 🎮 控制面板")
            st.markdown(f"**当前坐标系: {coord_sys}**")
            
            # ---------- 起点 A ----------
            st.markdown("#### 🚁 起点 A")
            if coord_sys == "GCJ-02 (高德/百度)":
                a_lat = st.number_input("纬度 (A)", value=st.session_state.A_lat_gcj, format="%.6f", key="a_lat")
                a_lng = st.number_input("经度 (A)", value=st.session_state.A_lng_gcj, format="%.6f", key="a_lng")
            else:
                wgs_lng, wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
                a_lat = st.number_input("纬度 (A)", value=wgs_lat, format="%.6f", key="a_lat_wgs")
                a_lng = st.number_input("经度 (A)", value=wgs_lng, format="%.6f", key="a_lng_wgs")
            if st.button("✅ 设置 A 点"):
                if coord_sys == "GCJ-02 (高德/百度)":
                    st.session_state.A_lat_gcj = a_lat
                    st.session_state.A_lng_gcj = a_lng
                else:
                    gcj_lng, gcj_lat = wgs84_to_gcj02(a_lng, a_lat)
                    st.session_state.A_lat_gcj = gcj_lat
                    st.session_state.A_lng_gcj = gcj_lng
                st.success("A点已更新")
            
            # ---------- 终点 B ----------
            st.markdown("#### 📍 终点 B")
            if coord_sys == "GCJ-02 (高德/百度)":
                b_lat = st.number_input("纬度 (B)", value=st.session_state.B_lat_gcj, format="%.6f", key="b_lat")
                b_lng = st.number_input("经度 (B)", value=st.session_state.B_lng_gcj, format="%.6f", key="b_lng")
            else:
                wgs_lng, wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
                b_lat = st.number_input("纬度 (B)", value=wgs_lat, format="%.6f", key="b_lat_wgs")
                b_lng = st.number_input("经度 (B)", value=wgs_lng, format="%.6f", key="b_lng_wgs")
            if st.button("✅ 设置 B 点"):
                if coord_sys == "GCJ-02 (高德/百度)":
                    st.session_state.B_lat_gcj = b_lat
                    st.session_state.B_lng_gcj = b_lng
                else:
                    gcj_lng, gcj_lat = wgs84_to_gcj02(b_lng, b_lat)
                    st.session_state.B_lat_gcj = gcj_lat
                    st.session_state.B_lng_gcj = gcj_lng
                st.success("B点已更新")
            
            # ---------- 飞行高度 ----------
            st.markdown("#### ✈️ 飞行参数")
            flight_h = st.number_input("设定飞行高度 (m)", value=st.session_state.flight_height, step=1)
            st.session_state.flight_height = flight_h
            
            st.markdown("---")
            st.markdown("#### 🧱 障碍物圈选与持久化")
            st.caption("在地图上使用多边形工具圈选障碍物区域")
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("💾 保存到文件"):
                    save_obstacles(st.session_state.obstacle_geojson)
                    st.success("障碍物配置已保存")
            with col_btn2:
                if st.button("📂 从文件加载"):
                    st.session_state.obstacle_geojson = load_obstacles()
                    st.success("已从文件加载障碍物")
                    st.rerun()
            with col_btn3:
                if st.button("🗑️ 清除全部"):
                    st.session_state.obstacle_geojson = {"type": "FeatureCollection", "features": []}
                    save_obstacles(st.session_state.obstacle_geojson)
                    st.success("已清除所有障碍物")
                    st.rerun()
            
            # 显示当前障碍物数量
            num_features = len(st.session_state.obstacle_geojson.get("features", []))
            st.write(f"**当前障碍物数量**: {num_features}")
            if num_features > 0:
                st.caption(f"保存时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 版本: v12.2")
        
        # ---------- 地图显示 (左列) ----------
        with left_col:
            st.markdown("### 🗺️ 卫星实况地图 (可绘制多边形圈选障碍物)")
            # 将A/B点转换为WGS-84用于地图显示
            A_wgs_lng, A_wgs_lat = gcj02_to_wgs84(st.session_state.A_lng_gcj, st.session_state.A_lat_gcj)
            B_wgs_lng, B_wgs_lat = gcj02_to_wgs84(st.session_state.B_lng_gcj, st.session_state.B_lat_gcj)
            center_lat = (A_wgs_lat + B_wgs_lat) / 2
            center_lng = (A_wgs_lng + B_wgs_lng) / 2
            
            # 创建地图
            folium_map = create_map(center_lat, center_lng, zoom_start=16)
            
            # 添加A/B点标记
            folium.Marker(
                location=[A_wgs_lat, A_wgs_lng],
                popup=f"起点 A<br>lat: {A_wgs_lat:.6f}<br>lng: {A_wgs_lng:.6f}",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(folium_map)
            folium.Marker(
                location=[B_wgs_lat, B_wgs_lng],
                popup=f"终点 B<br>lat: {B_wgs_lat:.6f}<br>lng: {B_wgs_lng:.6f}",
                icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa')
            ).add_to(folium_map)
            
            # 添加航线连线
            folium.PolyLine(
                locations=[[A_wgs_lat, A_wgs_lng], [B_wgs_lat, B_wgs_lng]],
                color='cyan',
                weight=4,
                opacity=0.8
            ).add_to(folium_map)
            
            # 添加已保存的障碍物多边形
            geojson_data = st.session_state.obstacle_geojson
            if geojson_data and geojson_data.get("features"):
                folium.GeoJson(
                    geojson_data,
                    name='障碍物区域',
                    style_function=lambda x: {'color': 'orange', 'weight': 3, 'fillOpacity': 0.3}
                ).add_to(folium_map)
            
            # 显示地图并获取绘制结果
            output = st_folium(
                folium_map,
                width=800,
                height=600,
                returned_objects=["last_active_drawing", "all_drawings"]
            )
            
            # 处理用户新绘制的多边形
            if output and "last_active_drawing" in output and output["last_active_drawing"]:
                drawing = output["last_active_drawing"]
                if drawing and drawing.get("geometry") and drawing["geometry"]["type"] == "Polygon":
                    # 将新绘制的多边形添加到 session_state 的 geojson 中
                    new_feature = {
                        "type": "Feature",
                        "geometry": drawing["geometry"],
                        "properties": {
                            "name": f"障碍物_{len(st.session_state.obstacle_geojson['features'])+1}",
                            "created": datetime.now().isoformat()
                        }
                    }
                    st.session_state.obstacle_geojson["features"].append(new_feature)
                    # 可选：自动保存
                    # save_obstacles(st.session_state.obstacle_geojson)
                    st.success("已添加新障碍物多边形")
                    st.rerun()
    
    # ==================== 飞行监控页面 ====================
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
        
        _, status_msg = heartbeat_status()
        if "超时" in status_msg:
            st.error(status_msg)
        elif "等待" in status_msg:
            st.info(status_msg)
        else:
            st.success(status_msg)
        
        if len(st.session_state.heartbeat_list) >= 2:
            df = pd.DataFrame(st.session_state.heartbeat_list, columns=["序号", "时间", "dt"])
            fig = px.line(df, x="时间", y="序号", title="📈 心跳序号变化趋势", markers=True)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        elif len(st.session_state.heartbeat_list) == 1:
            st.info("📊 已收到 1 个心跳包，继续接收后将显示趋势图")
        else:
            st.info("📊 等待无人机心跳数据...")
        
        if st.session_state.heartbeat_list:
            df_table = pd.DataFrame(st.session_state.heartbeat_list[-10:], columns=["序号", "时间", "dt"])
            st.dataframe(df_table.drop(columns=["dt"]), use_container_width=True)
        else:
            st.info("暂无心跳记录")
        
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
