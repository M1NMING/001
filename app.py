# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import math
from datetime import datetime

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台", layout="wide")

# ==================== 坐标系转换（GCJ-02 ↔ WGS-84）====================
def gcj02_to_wgs84(lng, lat):
    """GCJ-02 → WGS-84"""
    a = 6378245.0
    ee = 0.00669342162296594323
    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
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
    return lng * 2 - (lng + dlng), lat * 2 - (lat + dlat)

def wgs84_to_gcj02(lng, lat):
    """WGS-84 → GCJ-02"""
    a = 6378245.0
    ee = 0.00669342162296594323
    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
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

# ==================== 预设障碍物（校园内，GCJ-02）====================
OBSTACLES_GCJ = [
    {"name": "图书馆", "lng": 118.7505, "lat": 32.2330},
    {"name": "教学楼", "lng": 118.7512, "lat": 32.2338},
    {"name": "实验楼", "lng": 118.7498, "lat": 32.2345},
    {"name": "食堂",   "lng": 118.7483, "lat": 32.2329}
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

# ==================== 地图绘制（支持 Mapbox 或 3D 地球）====================
def render_mapbox_map(A_wgs, B_wgs, obstacles_wgs, token, height):
    """使用 Mapbox 卫星图 + 3D 俯仰角"""
    lats = [A_wgs[1], B_wgs[1]] + [o[0][1] for o in obstacles_wgs]
    lons = [A_wgs[0], B_wgs[0]] + [o[0][0] for o in obstacles_wgs]
    names = ["起点 A", "终点 B"] + [f"障碍物: {o[1]}" for o in obstacles_wgs]
    colors = ["green", "red"] + ["orange"] * len(obstacles_wgs)
    sizes = [15, 15] + [12] * len(obstacles_wgs)

    fig = go.Figure()
    fig.add_trace(go.Scattermapbox(
        lat=lats, lon=lons,
        mode="markers+text",
        marker=dict(size=sizes, color=colors),
        text=names, textposition="top center",
        name="关键点"
    ))
    fig.add_trace(go.Scattermapbox(
        lat=[A_wgs[1], B_wgs[1]], lon=[A_wgs[0], B_wgs[0]],
        mode="lines", line=dict(width=3, color="cyan"),
        name="规划航线"
    ))
    fig.update_layout(
        mapbox=dict(
            accesstoken=token,
            style="mapbox://styles/mapbox/satellite-streets-v12",
            center=dict(lat=(A_wgs[1]+B_wgs[1])/2, lon=(A_wgs[0]+B_wgs[0])/2),
            zoom=15, pitch=60, bearing=0
        ),
        margin=dict(l=0, r=0, t=30, b=0), height=600,
        title=f"🗺️ 3D 卫星地图 (飞行高度: {height} m)"
    )
    st.plotly_chart(fig, use_container_width=True)

def render_globe_map(A_wgs, B_wgs, obstacles_wgs, height):
    """无 Mapbox Token 时的备选：3D 地球仪（正交投影）"""
    lats = [A_wgs[1], B_wgs[1]] + [o[0][1] for o in obstacles_wgs]
    lons = [A_wgs[0], B_wgs[0]] + [o[0][0] for o in obstacles_wgs]
    names = ["起点 A", "终点 B"] + [f"障碍物: {o[1]}" for o in obstacles_wgs]
    colors = ["green", "red"] + ["orange"] * len(obstacles_wgs)

    fig = go.Figure()
    # 航线条（在大圆上绘制直线需要 mapbox，这里使用 scattergeo 的 lines）
    fig.add_trace(go.Scattergeo(
        lon=[A_wgs[0], B_wgs[0]], lat=[A_wgs[1], B_wgs[1]],
        mode="lines", line=dict(width=3, color="cyan"),
        name="规划航线"
    ))
    fig.add_trace(go.Scattergeo(
        lon=lons, lat=lats,
        mode="markers+text",
        marker=dict(size=12, color=colors),
        text=names, textposition="top center",
        name="关键点"
    ))
    fig.update_layout(
        geo=dict(
            projection_type="orthographic",   # 3D 地球仪
            showland=True, landcolor="lightgreen",
            showocean=True, oceancolor="lightblue",
            showcountries=True, countrycolor="gray",
            showcoastlines=True, coastlinecolor="black",
            center=dict(lat=(A_wgs[1]+B_wgs[1])/2, lon=(A_wgs[0]+B_wgs[0])/2),
            projection_rotation=dict(lon=(A_wgs[0]+B_wgs[0])/2, lat=(A_wgs[1]+B_wgs[1])/2),
            lonaxis_range=[A_wgs[0]-0.05, A_wgs[0]+0.05],  # 局部放大地图
            lataxis_range=[A_wgs[1]-0.05, A_wgs[1]+0.05]
        ),
        margin=dict(l=0, r=0, t=30, b=0), height=600,
        title=f"🌍 3D 地球模型 (飞行高度: {height} m)<br><sub>未提供 Mapbox Token，使用内置地球仪</sub>"
    )
    st.plotly_chart(fig, use_container_width=True)

def render_map(A_gcj, B_gcj, height, mapbox_token):
    """统一入口：将 GCJ-02 坐标转为 WGS-84，并根据 token 选择地图类型"""
    A_wgs = gcj02_to_wgs84(A_gcj[0], A_gcj[1])
    B_wgs = gcj02_to_wgs84(B_gcj[0], B_gcj[1])
    obstacles_wgs = [(gcj02_to_wgs84(o["lng"], o["lat"]), o["name"]) for o in OBSTACLES_GCJ]

    if mapbox_token and mapbox_token.strip() != "":
        render_mapbox_map(A_wgs, B_wgs, obstacles_wgs, mapbox_token.strip(), height)
    else:
        render_globe_map(A_wgs, B_wgs, obstacles_wgs, height)

# ==================== 页面路由 ====================
def main():
    st.sidebar.title("导航")
    page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

    # 公共侧边栏
    st.sidebar.markdown("---")
    st.sidebar.subheader("坐标系设置")
    coord_sys = st.sidebar.selectbox("输入坐标系", ["GCJ-02 (高德/百度)", "WGS-84"])
    mapbox_token = st.sidebar.text_input("Mapbox Token (选填，不填则用地球仪)", type="password",
                                         help="注册 mapbox.com 获取免费 token，留空将显示 3D 地球仪")
    st.sidebar.info("提示：若填了 Token 但仍无地图，请检查网络或 Token 有效性")

    # 初始化 A/B 点默认值（校园内 GCJ-02）
    if "A_lat" not in st.session_state:
        st.session_state.A_lat = 32.2322
        st.session_state.A_lng = 118.749
        st.session_state.B_lat = 32.2343
        st.session_state.B_lng = 118.749
        st.session_state.flight_height = 50

    if page == "航线规划":
        st.header("🗺️ 航线规划 (3D 地图)")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("起点 A")
            lat_a = st.number_input("纬度", value=st.session_state.A_lat, key="a_lat")
            lng_a = st.number_input("经度", value=st.session_state.A_lng, key="a_lng")
            if st.button("设置 A 点"):
                st.session_state.A_lat = lat_a
                st.session_state.A_lng = lng_a
                st.success(f"A 点已更新 ({lat_a}, {lng_a})")
        with col2:
            st.subheader("终点 B")
            lat_b = st.number_input("纬度", value=st.session_state.B_lat, key="b_lat")
            lng_b = st.number_input("经度", value=st.session_state.B_lng, key="b_lng")
            if st.button("设置 B 点"):
                st.session_state.B_lat = lat_b
                st.session_state.B_lng = lng_b
                st.success(f"B 点已更新 ({lat_b}, {lng_b})")

        st.session_state.flight_height = st.number_input("飞行高度 (m)", value=st.session_state.flight_height, step=5)

        # 坐标转换：根据用户选择的坐标系，转换为内部使用的 GCJ-02
        if coord_sys == "WGS-84":
            A_gcj = wgs84_to_gcj02(lng_a, lat_a)
            B_gcj = wgs84_to_gcj02(lng_b, lat_b)
        else:
            A_gcj = (lng_a, lat_a)
            B_gcj = (lng_b, lat_b)

        render_map(A_gcj, B_gcj, st.session_state.flight_height, mapbox_token)

        with st.expander("📌 障碍物列表 (校园内 GCJ-02)"):
            for obs in OBSTACLES_GCJ:
                st.write(f"- {obs['name']}: ({obs['lng']}, {obs['lat']})")

    elif page == "飞行监控":
        st.header("📡 飞行监控 - 心跳包实时监测")
        init_heartbeat()
        enable = st.sidebar.checkbox("🚁 允许无人机发送心跳", value=True, key="hb_enable")
        update_heartbeat(enable)

        diff, msg = heartbeat_status()
        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("最新心跳序号", latest[0])
            col2.metric("最新心跳时间", latest[1])
        else:
            col1.metric("最新心跳序号", "无")
            col2.metric("最新心跳时间", "无")

        if "超时" in msg:
            st.error(msg)
        elif "等待" in msg:
            st.info(msg)
        else:
            st.success(msg)

        if len(st.session_state.heartbeat_list) >= 2:
            df = pd.DataFrame(st.session_state.heartbeat_list, columns=["序号", "时间", "dt"])
            fig = px.line(df, x="时间", y="序号", title="📈 心跳序号变化趋势",
                          markers=True, labels={"序号": "心跳序号", "时间": "接收时间"})
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)
        elif len(st.session_state.heartbeat_list) == 1:
            st.info("📊 已收到 1 个心跳，继续接收后显示折线图")
        else:
            st.info("📊 等待心跳数据...")

        if st.session_state.heartbeat_list:
            df_table = pd.DataFrame(st.session_state.heartbeat_list[-10:], columns=["序号", "时间", "dt"])
            st.dataframe(df_table.drop(columns=["dt"]), use_container_width=True)
        else:
            st.info("暂无心跳记录")

        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
