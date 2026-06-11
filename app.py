import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from urllib.parse import urlencode

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 高德3D卫星地图", layout="wide")

# ==================== 坐标系转换 ====================
# 高德地图使用 GCJ-02 坐标系，WGS-84 转 GCJ-02（简化算法）
def wgs84_to_gcj02(lng, lat):
    """WGS-84 → GCJ-02（火星坐标系）"""
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

# ==================== 预设障碍物（校园内，GCJ-02 坐标）====================
OBSTACLES_GCJ = [
    {"name": "🏛️ 图书馆", "lng": 118.7505, "lat": 32.2330},
    {"name": "📖 教学楼", "lng": 118.7512, "lat": 32.2338},
    {"name": "🧪 实验楼", "lng": 118.7498, "lat": 32.2345},
    {"name": "🍽️ 食堂",   "lng": 118.7483, "lat": 32.2329}
]

# ==================== 心跳监测 ====================
def init_heartbeat():
    if "heartbeat_list" not in st.session_state:
        st.session_state.heartbeat_list = []   # [序号, 时间字符串, datetime对象]
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

# ==================== 高德地图生成函数（核心）====================
def generate_amap_html(A_lng, A_lat, B_lng, B_lat, obstacles, map_key=""):
    """
    生成包含高德 3D 卫星地图的完整 HTML 页面
    参数：
      A_lng, A_lat: 起点 A (GCJ-02)
      B_lng, B_lat: 终点 B (GCJ-02)
      obstacles: 障碍物列表 [{"name":"xx", "lng":xx, "lat":xx}, ...]
      map_key: 高德 API Key，留空可使用无 Key 模式（功能受限，建议申请）
    """
    
    obstacles_js = "[\n" + ",\n".join([
        f'{{name: "{obs['name']}", lng: {obs['lng']}, lat: {obs['lat']}}}'
        for obs in obstacles
    ]) + "\n]"
    
    # 障碍物数量多时，提高渲染性能，仅显示点位与名称
    # 连接线 A-B
    # 地图中心点为 A 和 B 的中点
    center_lng = (A_lng + B_lng) / 2
    center_lat = (A_lat + B_lat) / 2
    
    # 计算合适的缩放级别：根据 A-B 的经纬度跨度估算，跨度约 0.002，适合 zoom=17
    zoom_lv = 17
    
    # 完整的 HTML 代码
    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>南京科技职业学院无人机航线规划 | 高德3D卫星地图</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            overflow: hidden;
        }}
        #container {{
            width: 100%;
            height: 100%;
            background-color: #000;
        }}
        .info-panel {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            font-size: 12px;
            font-family: monospace;
            z-index: 1000;
            backdrop-filter: blur(5px);
            pointer-events: none;
            border-left: 4px solid #00ff00;
        }}
        .title-bar {{
            position: absolute;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            color: #ffaa00;
            padding: 6px 20px;
            border-radius: 30px;
            font-size: 14px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
            z-index: 1000;
            pointer-events: none;
            white-space: nowrap;
            backdrop-filter: blur(5px);
            border: 1px solid #ffaa00;
        }}
        @keyframes pulse {{
            0% {{ opacity: 0.6; transform: scale(0.8); }}
            100% {{ opacity: 1; transform: scale(1.2); }}
        }}
        .start-marker::after, .end-marker::after {{
            content: '';
            position: absolute;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            animation: pulse 1s infinite;
        }}
    </style>
    <script src="https://webapi.amap.com/maps?v=2.0&key={map_key}&plugin=AMap.ToolBar,AMap.ControlBar"></script>
    <!-- 如果无 Key，高德会降级显示基础地图，但仍可工作 -->
    <script>
    let map, startMarker, endMarker, linePolyline;
    const obstacles = {obstacles_js};
    
    // 坐标
    const A_POINT = {{ lng: {A_lng}, lat: {A_lat}, name: "🟢 起点 A" }};
    const B_POINT = {{ lng: {B_lng}, lat: {B_lat}, name: "🔴 终点 B" }};
    const CENTER = {{ lng: {center_lng}, lat: {center_lat} }};
    
    window.onload = function() {{
        // 创建地图，开启 3D 视图和卫星图
        map = new AMap.Map('container', {{
            viewMode: '3D',           // 3D 地图模式
            pitch: 55,                // 俯仰角 55 度，呈现更真实的三维视野
            rotateEnable: true,       // 允许旋转
            zoom: {zoom_lv},
            center: [CENTER.lng, CENTER.lat],
            layers: [
                new AMap.TileLayer.Satellite(),   // 高德卫星影像图
                new AMap.TileLayer.RoadNet()      // 叠加路网图层，增强可读性
            ]
        }});
        
        // 添加控制控件
        map.addControl(new AMap.ToolBar({{ position: 'RT' }}));
        map.addControl(new AMap.ControlBar({{ position: 'RB' }}));
        
        // 创建自定义点标记样式
        // 起点 A 绿色大图标
        startMarker = new AMap.Marker({{
            position: [A_POINT.lng, A_POINT.lat],
            title: A_POINT.name,
            label: {{
                offset: new AMap.Pixel(0, -30),
                content: `<div style="background:#00cc66; color:white; padding:2px 8px; border-radius:20px; font-size:12px; font-weight:bold; box-shadow:0 2px 6px rgba(0,0,0,0.3);">🚁 A点</div>`
            }},
            icon: new AMap.Icon({{
                size: new AMap.Size(30, 30),
                image: "https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png",
                imageSize: new AMap.Size(30, 30)
            }}),
            offset: new AMap.Pixel(-15, -30)
        }});
        startMarker.setMap(map);
        
        // 终点 B 红色大图标
        endMarker = new AMap.Marker({{
            position: [B_POINT.lng, B_POINT.lat],
            title: B_POINT.name,
            label: {{
                offset: new AMap.Pixel(0, -30),
                content: `<div style="background:#ff4444; color:white; padding:2px 8px; border-radius:20px; font-size:12px; font-weight:bold; box-shadow:0 2px 6px rgba(0,0,0,0.3);">🎯 B点</div>`
            }},
            icon: new AMap.Icon({{
                size: new AMap.Size(30, 30),
                image: "https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png",
                imageSize: new AMap.Size(30, 30)
            }}),
            offset: new AMap.Pixel(-15, -30)
        }});
        endMarker.setMap(map);
        
        // 绘制 A-B 连线（航线条）
        const lineArr = [
            [A_POINT.lng, A_POINT.lat],
            [B_POINT.lng, B_POINT.lat]
        ];
        linePolyline = new AMap.Polyline({{
            path: lineArr,
            strokeColor: "#00ffff",
            strokeWeight: 4,
            strokeOpacity: 0.9,
            strokeStyle: "solid",
            lineJoin: "round",
            lineCap: "round",
            zIndex: 10
        }});
        linePolyline.setMap(map);
        
        // 添加障碍物标记（橙色图标）
        for (let obs of obstacles) {{
            let obsMarker = new AMap.Marker({{
                position: [obs.lng, obs.lat],
                title: obs.name,
                label: {{
                    offset: new AMap.Pixel(0, -20),
                    content: `<div style="background:#ff8800; color:#000; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:bold;">⚠️ ${{obs.name}}</div>`
                }},
                icon: new AMap.Icon({{
                    size: new AMap.Size(24, 24),
                    image: "https://webapi.amap.com/theme/v1.3/markers/n/mark_c.png",
                    imageSize: new AMap.Size(24, 24)
                }}),
                offset: new AMap.Pixel(-12, -24)
            }});
            obsMarker.setMap(map);
        }}
        
        // 添加一段提示信息（点击地图可显示经纬度，调试用）
        map.on('click', function(e) {{
            console.log("点击坐标:", e.lnglat.getLng(), e.lnglat.getLat());
        }});
        
        // 自动将视角调整到最佳视野范围，包含 A 和 B 点以及障碍物
        let bounds = new AMap.Bounds([A_POINT.lng, A_POINT.lat], [B_POINT.lng, B_POINT.lat]);
        for (let obs of obstacles) {{
            bounds.extend([obs.lng, obs.lat]);
        }}
        map.setBounds(bounds, false, [50, 50, 50, 50]);  // 调整边距
        map.setZoomAndCenter(17, [CENTER.lng, CENTER.lat]);  // 为了 3D 效果，保持较高视角
    }};
    </script>
</head>
<body>
    <div id="container"></div>
    <div class="title-bar">
        ✈️ 南京科技职业学院无人机航线规划 | 高德 3D 卫星影像
    </div>
    <div class="info-panel">
        🟢 起点 A: ({A_lat}, {A_lng})<br>
        🔴 终点 B: ({B_lat}, {B_lng})<br>
        📍 障碍物: {len(obstacles)} 处校园建筑 · 航线用青色连线标示<br>
        🖱️ 鼠标拖拽旋转视角 / 右键拖动倾斜 / 滚轮缩放
    </div>
</body>
</html>
    """
    return html_code


# ==================== 页面路由 ====================
def main():
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (高德3D卫星地图)", "📡 飞行监控 (心跳监测)"])
    
    # 侧边栏配置
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ 坐标系与地图设置")
    coord_sys = st.sidebar.selectbox("输入坐标系", ["GCJ-02 (高德火星坐标)", "WGS-84 (GPS/北斗)"])
    amap_key = st.sidebar.text_input("高德地图 API Key (必填，免费申请)", type="password",
                                     help="申请地址：https://lbs.amap.com/ ，创建应用获取 Key，Web端(JS API)服务类型")
    
    # 若未填 Key 给出提示，但地图仍然会降级显示
    if not amap_key:
        st.sidebar.warning("⚠️ 未填写高德 API Key，地图功能受限或无法加载卫星图。请在高德开放平台免费申请 Key。")
    else:
        st.sidebar.success("✅ 已配置高德 API Key")
    
    # 初始化 A/B 点默认值（校园内 GCJ-02，南京科技职业学院中心）
    if "A_lat" not in st.session_state:
        st.session_state.A_lat = 32.2322
        st.session_state.A_lng = 118.749
        st.session_state.B_lat = 32.2343
        st.session_state.B_lng = 118.749
        st.session_state.flight_height = 50
    
    if page == "🗺️ 航线规划 (高德3D卫星地图)":
        st.header("🗺️ 南京科技职业学院 无人机航线规划 (高德3D卫星地图)")
        st.caption("基于高德 JS API 2.0 的 3D 卫星影像地图，支持 3D 视图、鼠标拖拽旋转/倾斜、自动航线连线、障碍物标注等功能。")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚁 起点 A")
            lat_a = st.number_input("纬度", value=st.session_state.A_lat, key="a_lat", format="%.6f")
            lng_a = st.number_input("经度", value=st.session_state.A_lng, key="a_lng", format="%.6f")
            if st.button("✅ 设置 A 点", key="set_a"):
                st.session_state.A_lat = lat_a
                st.session_state.A_lng = lng_a
                st.success(f"A 点已更新 ({lat_a:.6f}, {lng_a:.6f})")
        with col2:
            st.subheader("📍 终点 B")
            lat_b = st.number_input("纬度", value=st.session_state.B_lat, key="b_lat", format="%.6f")
            lng_b = st.number_input("经度", value=st.session_state.B_lng, key="b_lng", format="%.6f")
            if st.button("✅ 设置 B 点", key="set_b"):
                st.session_state.B_lat = lat_b
                st.session_state.B_lng = lng_b
                st.success(f"B 点已更新 ({lat_b:.6f}, {lng_b:.6f})")
        
        flight_height = st.number_input("✈️ 设定飞行高度 (m)（仅用于显示）", value=st.session_state.flight_height, step=5)
        st.session_state.flight_height = flight_height
        
        # 根据用户选择的坐标系，统一转换为 GCJ-02（高德地图内部使用 GCJ-02）
        if coord_sys == "WGS-84 (GPS/北斗)":
            A_lng_gcj, A_lat_gcj = wgs84_to_gcj02(lng_a, lat_a)
            B_lng_gcj, B_lat_gcj = wgs84_to_gcj02(lng_b, lat_b)
            st.info(f"🔁 坐标转换：输入为 WGS-84 → 已自动转换为 GCJ-02（高德火星坐标），A点({A_lat_gcj:.6f}, {A_lng_gcj:.6f})，B点({B_lat_gcj:.6f}, {B_lng_gcj:.6f})")
        else:
            A_lng_gcj, A_lat_gcj = lng_a, lat_a
            B_lng_gcj, B_lat_gcj = lng_b, lat_b
        
        # 障碍物坐标已是 GCJ-02，无需转换
        obs_for_map = OBSTACLES_GCJ
        
        # 生成高德地图 HTML 并嵌入
        if amap_key:
            map_html = generate_amap_html(A_lng_gcj, A_lat_gcj, B_lng_gcj, B_lat_gcj, obs_for_map, amap_key)
        else:
            # 无 Key 时仍然生成，但高德 JS API 会限制部分图层，卫星图可能不显示
            st.warning("⚠️ 未填写高德 API Key，地图无法显示卫星影像，请在上方侧边栏配置 Key 以使用完整功能。")
            map_html = generate_amap_html(A_lng_gcj, A_lat_gcj, B_lng_gcj, B_lat_gcj, obs_for_map, "")
        
        # 使用 components.html 渲染高德地图（全尺寸 3D 交互地图）
        from streamlit.components.v1 import html
        html(map_html, height=650, scrolling=False)
        
        # 显示额外信息
        with st.expander("📌 校园障碍物列表 (GCJ-02 坐标)"):
            for obs in OBSTACLES_GCJ:
                st.write(f"- {obs['name']}: 经度 {obs['lng']}, 纬度 {obs['lat']}")
    
    elif page == "📡 飞行监控 (心跳监测)":
        st.header("📡 无人机心跳监测 · 实时飞行数据")
        init_heartbeat()
        enable_sending = st.sidebar.checkbox("🚁 允许无人机发送心跳包", value=True, key="hb_enable")
        update_heartbeat(enable_sending)
        
        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("💓 最新心跳序号", latest[0])
            col2.metric("⏱️ 最新心跳时间", latest[1])
        else:
            col1.metric("💓 最新心跳序号", "无")
            col2.metric("⏱️ 最新心跳时间", "无")
        
        diff, status_msg = heartbeat_status()
        if "超时" in status_msg:
            st.error(status_msg)
        elif "等待" in status_msg:
            st.info(status_msg)
        else:
            st.success(status_msg)
        
        # 折线图（心跳序号变化）
        if len(st.session_state.heartbeat_list) >= 2:
            df = pd.DataFrame(st.session_state.heartbeat_list, columns=["序号", "时间", "dt"])
            fig = px.line(df, x="时间", y="序号", title="📈 心跳序号变化趋势 (实时)",
                          markers=True, labels={"序号": "心跳序号", "时间": "接收时间"})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        elif len(st.session_state.heartbeat_list) == 1:
            st.info("📊 已收到 1 个心跳包，继续接收后显示趋势图")
        else:
            st.info("📊 等待无人机心跳数据...")
        
        # 数据表格（最近 10 条）
        if st.session_state.heartbeat_list:
            df_table = pd.DataFrame(st.session_state.heartbeat_list[-10:], columns=["序号", "时间", "dt"])
            st.dataframe(df_table.drop(columns=["dt"]), use_container_width=True, hide_index=True)
        else:
            st.info("暂无心跳记录")
        
        # 自动刷新（每秒）
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
