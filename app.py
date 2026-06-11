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

# ==================== 坐标系转换 ====================
# GCJ-02 与 WGS-84 互转（简化算法，精度足够演示）
def gcj02_to_wgs84(lng, lat):
    """GCJ-02(火星坐标系) 转 WGS-84"""
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
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat

def wgs84_to_gcj02(lng, lat):
    """WGS-84 转 GCJ-02（反向，同上算法）"""
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
    mglat = lat + dlat
    mglng = lng + dlng
    return mglng, mglat

# ==================== 预设障碍物（位于校园内，通用坐标） ====================
# 这些障碍物是相对于校园（例如南京某大学）的固定点，单位为 GCJ-02 度
OBSTACLES_GCJ = [
    {"name": "图书馆", "lng": 118.7505, "lat": 32.2330},
    {"name": "教学楼", "lng": 118.7512, "lat": 32.2338},
    {"name": "实验楼", "lng": 118.7498, "lat": 32.2345},
    {"name": "食堂",    "lng": 118.7483, "lat": 32.2329}
]

# ==================== 心跳监测相关逻辑 ====================
def init_heartbeat_state():
    if "heartbeat_list" not in st.session_state:
        st.session_state.heartbeat_list = []
    if "last_gen_time" not in st.session_state:
        st.session_state.last_gen_time = None
    if "seq_counter" not in st.session_state:
        st.session_state.seq_counter = 0

def update_heartbeat(enable_sending):
    now = datetime.now()
    if enable_sending:
        if (st.session_state.last_gen_time is None or
                (now - st.session_state.last_gen_time).total_seconds() >= 1):
            st.session_state.seq_counter += 1
            heartbeat = [st.session_state.seq_counter, now.strftime("%H:%M:%S"), now]
            st.session_state.heartbeat_list.append(heartbeat)
            st.session_state.last_gen_time = now
            if len(st.session_state.heartbeat_list) > 300:
                st.session_state.heartbeat_list.pop(0)

def get_heartbeat_status():
    if not st.session_state.heartbeat_list:
        return None, "⏳ 等待首个心跳包..."
    last_time = st.session_state.heartbeat_list[-1][2]
    diff = (datetime.now() - last_time).total_seconds()
    if diff > 3:
        return diff, f"⚠️ 连接超时！已 {diff:.1f} 秒未收到心跳包"
    else:
        return diff, f"✅ 连接正常，最后心跳: {diff:.1f} 秒前"

# ==================== 地图绘制函数 ====================
def render_3d_map(A_gcj, B_gcj, flight_height, mapbox_token):
    """
    A_gcj, B_gcj: GCJ-02 坐标 (lng, lat)
    flight_height: 飞行高度(m)，此处仅用于显示在标注中
    """
    # 转换到 WGS-84 供 Mapbox 使用
    A_wgs = gcj02_to_wgs84(A_gcj[0], A_gcj[1])
    B_wgs = gcj02_to_wgs84(B_gcj[0], B_gcj[1])
    obstacles_wgs = [(gcj02_to_wgs84(o["lng"], o["lat"]), o["name"]) for o in OBSTACLES_GCJ]

    # 创建散点数据
    lat_list = [A_wgs[1], B_wgs[1]]
    lon_list = [A_wgs[0], B_wgs[0]]
    names = ["起点 A", "终点 B"]
    colors = ["green", "red"]
    sizes = [15, 15]

    for (lng, lat), name in obstacles_wgs:
        lat_list.append(lat)
        lon_list.append(lng)
        names.append(f"障碍物: {name}")
        colors.append("orange")
        sizes.append(12)

    # 连线数据（A->B）
    line_lons = [A_wgs[0], B_wgs[0]]
    line_lats = [A_wgs[1], B_wgs[1]]

    fig = go.Figure()

    # 添加障碍物和起终点的散点
    fig.add_trace(go.Scattermapbox(
        lat=lat_list,
        lon=lon_list,
        mode="markers+text",
        marker=dict(size=sizes, color=colors, symbol="circle"),
        text=names,
        textposition="top center",
        hoverinfo="text",
        name="关键点"
    ))

    # 添加航线（连线）
    fig.add_trace(go.Scattermapbox(
        lat=line_lats,
        lon=line_lons,
        mode="lines",
        line=dict(width=3, color="cyan"),
        name="规划航线"
    ))

    # 地图布局（启用3D地形）
    fig.update_layout(
        mapbox=dict(
            accesstoken=mapbox_token,
            style="mapbox://styles/mapbox/satellite-streets-v12",  # 卫星图带地形
            center=dict(lat=(A_wgs[1]+B_wgs[1])/2, lon=(A_wgs[0]+B_wgs[0])/2),
            zoom=15,
            pitch=60,       # 俯仰角，呈现3D效果
            bearing=0,
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=600,
        title=f"航线规划 (飞行高度: {flight_height} m)"
    )

    st.plotly_chart(fig, use_container_width=True)

# ==================== 页面路由 ====================
def page_route():
    st.sidebar.title("导航")
    page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

    # 坐标系设置放在侧边栏
    st.sidebar.markdown("---")
    st.sidebar.subheader("坐标系设置")
    coord_sys = st.sidebar.selectbox("输入坐标系", ["GCJ-02 (高德/百度)", "WGS-84"], index=0)
    mapbox_token = st.sidebar.text_input("Mapbox Token (免费申请)", type="password",
                                         help="请前往 mapbox.com 申请，填入后地图才能显示")
    st.sidebar.info("若地图无法显示，请检查 Token 是否正确，并确保输入坐标位于学校内。")

    # 公共：起点/终点输入（使用会话状态保留）
    if "A_lat" not in st.session_state:
        st.session_state.A_lat = 32.2322
        st.session_state.A_lng = 118.749
        st.session_state.B_lat = 32.2343
        st.session_state.B_lng = 118.749
        st.session_state.flight_height = 50

    if page == "航线规划":
        st.header("🗺️ 航线规划 (3D地图)")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("起点 A")
            new_A_lat = st.number_input("纬度 (GCJ-02)", value=st.session_state.A_lat, key="a_lat_in")
            new_A_lng = st.number_input("经度 (GCJ-02)", value=st.session_state.A_lng, key="a_lng_in")
            if st.button("设置 A 点"):
                st.session_state.A_lat = new_A_lat
                st.session_state.A_lng = new_A_lng
                st.success(f"A 点已设为 ({new_A_lat}, {new_A_lng})")
        with col2:
            st.subheader("终点 B")
            new_B_lat = st.number_input("纬度 (GCJ-02)", value=st.session_state.B_lat, key="b_lat_in")
            new_B_lng = st.number_input("经度 (GCJ-02)", value=st.session_state.B_lng, key="b_lng_in")
            if st.button("设置 B 点"):
                st.session_state.B_lat = new_B_lat
                st.session_state.B_lng = new_B_lng
                st.success(f"B 点已设为 ({new_B_lat}, {new_B_lng})")

        st.session_state.flight_height = st.number_input("设定飞行高度 (m)", value=st.session_state.flight_height, step=5)

        # 确保坐标在合理范围内（学校内约 118.74~118.76, 32.23~32.24）
        if not mapbox_token:
            st.warning("请提供有效的 Mapbox Token 以显示 3D 地图。")
        else:
            A_gcj = (st.session_state.A_lng, st.session_state.A_lat)
            B_gcj = (st.session_state.B_lng, st.session_state.B_lat)
            render_3d_map(A_gcj, B_gcj, st.session_state.flight_height, mapbox_token)

        with st.expander("📌 障碍物列表（校园内固定建筑）"):
            for obs in OBSTACLES_GCJ:
                st.write(f"- {obs['name']}: 经度 {obs['lng']}, 纬度 {obs['lat']} (GCJ-02)")

    elif page == "飞行监控":
        st.header("📡 飞行监控 - 心跳包实时监测")
        init_heartbeat_state()
        enable_sending = st.sidebar.checkbox("🚁 允许无人机发送心跳", value=True, key="heartbeat_toggle")

        # 模拟生成心跳（基于时间差）
        update_heartbeat(enable_sending)

        # 显示状态
        diff, status_msg = get_heartbeat_status()
        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("最新心跳序号", latest[0])
            col2.metric("最新心跳时间", latest[1])
        else:
            col1.metric("最新心跳序号", "无")
            col2.metric("最新心跳时间", "无")

        if "超时" in status_msg:
            st.error(status_msg)
        elif "等待" in status_msg:
            st.info(status_msg)
        else:
            st.success(status_msg)

        # 折线图
        if len(st.session_state.heartbeat_list) >= 2:
            df = pd.DataFrame(st.session_state.heartbeat_list, columns=["序号", "时间", "datetime_obj"])
            df["时间标签"] = df["时间"]
            fig = px.line(df, x="时间标签", y="序号", title="📈 心跳序号变化趋势",
                          labels={"序号": "心跳序号", "时间标签": "接收时间"}, markers=True)
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)
        elif len(st.session_state.heartbeat_list) == 1:
            st.info("📊 收集到1个心跳包，继续接收后将显示折线图...")
        else:
            st.info("📊 等待心跳包数据，折线图即将显示...")

        # 表格
        if st.session_state.heartbeat_list:
            display_df = pd.DataFrame(st.session_state.heartbeat_list[-10:], columns=["序号", "时间", "datetime_obj"])
            display_df = display_df.drop(columns=["datetime_obj"])
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("暂无心跳记录")

        # 自动刷新（每秒）
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    page_route()
