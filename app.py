import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 高德3D卫星地图", layout="wide")

# ==================== 坐标系转换 ====================
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

# ==================== 预设障碍物（校园内，GCJ-02）====================
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

# ==================== 高德地图 HTML 生成（带错误处理）====================
def generate_amap_html(A_lng, A_lat, B_lng, B_lat, obstacles, api_key):
    """生成带错误检测的高德地图HTML，若key无效则显示错误信息"""
    center_lng = (A_lng + B_lng) / 2
    center_lat = (A_lat + B_lat) / 2

    obstacles_js = "[\n" + ",\n".join([
        f'{{name: "{obs['name']}", lng: {obs['lng']}, lat: {obs['lat']}}}'
        for obs in obstacles
    ]) + "\n]"

    # 若没有提供 Key，直接显示错误提示（不加载高德 API）
    if not api_key or api_key.strip() == "":
        return f"""
        <div style="width:100%; height:100%; background:#1e1e1e; display:flex; align-items:center; justify-content:center; color:white; font-family:monospace; flex-direction:column;">
            <h3>⚠️ 高德地图 API Key 未配置</h3>
            <p>请在左侧边栏输入您申请的高德 Web 端 Key。</p>
            <p>👉 <a href="https://lbs.amap.com/" target="_blank" style="color:#00aaff;">点击申请免费 Key</a>（选择 Web端(JS API)）</p>
            <p>申请后复制 Key 粘贴到侧边栏输入框，地图将自动显示。</p>
        </div>
        """

    # 生成完整 HTML，加入错误回调
    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>南京科技职业学院 | 高德3D卫星地图</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body, #container {{ width: 100%; height: 100%; overflow: hidden; background: #0a2f3a; }}
        #error-msg {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.85);
            color: #ff8888;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            z-index: 1000;
            font-family: sans-serif;
            display: none;
            border-left: 4px solid #ff0000;
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
        }}
    </style>
    <script src="https://webapi.amap.com/maps?v=2.0&key={api_key}&plugin=AMap.ToolBar,AMap.ControlBar"></script>
    <script>
    let map;
    let loadError = false;
    window.onload = function() {{
        // 检查 AMap 是否加载成功
        if (typeof AMap === 'undefined' || !AMap.Map) {{
            document.getElementById('error-msg').style.display = 'block';
            document.getElementById('error-msg').innerHTML = '高德 API 加载失败，请检查网络或 API Key 是否正确。<br>确保 Key 的服务平台为 "Web端(JS API)"。';
            return;
        }}
        try {{
            const A = {{ lng: {A_lng}, lat: {A_lat} }};
            const B = {{ lng: {B_lng}, lat: {B_lat} }};
            const center = {{ lng: {center_lng}, lat: {center_lat} }};
            const obstacles = {obstacles_js};

            map = new AMap.Map('container', {{
                viewMode: '3D',
                pitch: 55,
                rotateEnable: true,
                zoom: 17,
                center: [center.lng, center.lat],
                layers: [
                    new AMap.TileLayer.Satellite(),
                    new AMap.TileLayer.RoadNet()
                ]
            }});

            map.addControl(new AMap.ToolBar({{ position: 'RT' }}));
            map.addControl(new AMap.ControlBar({{ position: 'RB' }}));

            // 起点标记
            new AMap.Marker({{
                position: [A.lng, A.lat],
                label: {{ offset: new AMap.Pixel(0, -30), content: '<div style="background:#00cc66; padding:2px 8px; border-radius:20px; font-weight:bold;">🚁 A点</div>' }},
                icon: new AMap.Icon({{ size: new AMap.Size(30,30), image: "https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png", imageSize: new AMap.Size(30,30) }})
            }}).setMap(map);

            // 终点标记
            new AMap.Marker({{
                position: [B.lng, B.lat],
                label: {{ offset: new AMap.Pixel(0, -30), content: '<div style="background:#ff4444; padding:2px 8px; border-radius:20px; font-weight:bold;">🎯 B点</div>' }},
                icon: new AMap.Icon({{ size: new AMap.Size(30,30), image: "https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png", imageSize: new AMap.Size(30,30) }})
            }}).setMap(map);

            // 航线连线
            new AMap.Polyline({{
                path: [[A.lng, A.lat], [B.lng, B.lat]],
                strokeColor: "#00ffff", strokeWeight: 4, strokeOpacity: 0.9
            }}).setMap(map);

            // 障碍物
            for (let obs of obstacles) {{
                new AMap.Marker({{
                    position: [obs.lng, obs.lat],
                    label: {{ offset: new AMap.Pixel(0, -20), content: `<div style="background:#ff8800; padding:2px 8px; border-radius:20px;">⚠️ ${{obs.name}}</div>` }},
                    icon: new AMap.Icon({{ size: new AMap.Size(24,24), image: "https://webapi.amap.com/theme/v1.3/markers/n/mark_c.png", imageSize: new AMap.Size(24,24) }})
                }}).setMap(map);
            }}

            // 自动调整视野
            let bounds = new AMap.Bounds([A.lng, A.lat], [B.lng, B.lat]);
            obstacles.forEach(o => bounds.extend([o.lng, o.lat]));
            map.setBounds(bounds, false, [50,50,50,50]);
            
        }} catch(e) {{
            document.getElementById('error-msg').style.display = 'block';
            document.getElementById('error-msg').innerHTML = '地图初始化出错: ' + e.message;
        }}
    }};
    // 高德 API 异步加载失败时的捕获（通过超时检测）
    setTimeout(function() {{
        if (typeof AMap === 'undefined' || !map) {{
            let errDiv = document.getElementById('error-msg');
            if (errDiv) {{
                errDiv.style.display = 'block';
                errDiv.innerHTML = '地图加载超时，请检查网络或 API Key 是否有效。';
            }}
        }}
    }}, 5000);
    </script>
</head>
<body>
    <div id="container"></div>
    <div id="error-msg" style="display:none;"></div>
    <div class="title-bar">✈️ 南京科技职业学院 | 高德3D卫星影像</div>
    <div class="info-panel">
        🟢 A: ({A_lat:.6f}, {A_lng:.6f})<br>
        🔴 B: ({B_lat:.6f}, {B_lng:.6f})<br>
        📍 障碍物: {len(obstacles)}处校园建筑
    </div>
</body>
</html>
    """
    return html_code

# ==================== 页面主体 ====================
def main():
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (高德3D卫星图)", "📡 飞行监控 (心跳监测)"])

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ 地图设置")
    coord_sys = st.sidebar.selectbox("输入坐标系", ["GCJ-02 (高德火星坐标)", "WGS-84 (GPS/北斗)"])
    amap_key = st.sidebar.text_input("高德地图 Web端 API Key", type="password",
                                     help="必须申请！地址：https://lbs.amap.com/ ，创建应用时选择「Web端(JS API)」")
    
    if not amap_key:
        st.sidebar.error("❌ 未提供有效的高德 API Key，地图将无法显示。")
    else:
        st.sidebar.success("✅ 已配置高德 Key")

    # 初始化坐标
    if "A_lat" not in st.session_state:
        st.session_state.A_lat = 32.2322
        st.session_state.A_lng = 118.749
        st.session_state.B_lat = 32.2343
        st.session_state.B_lng = 118.749
        st.session_state.flight_height = 50

    if page == "🗺️ 航线规划 (高德3D卫星图)":
        st.header("🗺️ 南京科技职业学院 无人机航线规划")
        st.caption("高德 3D 卫星影像地图 | 鼠标拖拽平移、右键倾斜、Ctrl+左键旋转")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚁 起点 A")
            lat_a = st.number_input("纬度", value=st.session_state.A_lat, key="a_lat", format="%.6f")
            lng_a = st.number_input("经度", value=st.session_state.A_lng, key="a_lng", format="%.6f")
            if st.button("✅ 设置 A 点"):
                st.session_state.A_lat = lat_a
                st.session_state.A_lng = lng_a
                st.success(f"A 点已更新")
        with col2:
            st.subheader("📍 终点 B")
            lat_b = st.number_input("纬度", value=st.session_state.B_lat, key="b_lat", format="%.6f")
            lng_b = st.number_input("经度", value=st.session_state.B_lng, key="b_lng", format="%.6f")
            if st.button("✅ 设置 B 点"):
                st.session_state.B_lat = lat_b
                st.session_state.B_lng = lng_b
                st.success(f"B 点已更新")

        flight_height = st.number_input("✈️ 飞行高度 (m)", value=st.session_state.flight_height, step=5)
        st.session_state.flight_height = flight_height

        # 坐标转换
        if coord_sys == "WGS-84 (GPS/北斗)":
            A_lng_gcj, A_lat_gcj = wgs84_to_gcj02(lng_a, lat_a)
            B_lng_gcj, B_lat_gcj = wgs84_to_gcj02(lng_b, lat_b)
            st.info(f"🔁 已转换至 GCJ-02：A({A_lat_gcj:.6f}, {A_lng_gcj:.6f})  B({B_lat_gcj:.6f}, {B_lng_gcj:.6f})")
        else:
            A_lng_gcj, A_lat_gcj = lng_a, lat_a
            B_lng_gcj, B_lat_gcj = lng_b, lat_b

        # 生成地图（若 key 无效，HTML 内部会显示错误）
        map_html = generate_amap_html(A_lng_gcj, A_lat_gcj, B_lng_gcj, B_lat_gcj, OBSTACLES_GCJ, amap_key)
        html(map_html, height=650, scrolling=False)

        with st.expander("📌 校园障碍物列表 (GCJ-02)"):
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
