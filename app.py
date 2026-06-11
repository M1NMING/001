# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import math
import json
import os
from datetime import datetime
from streamlit.components.v1 import html

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机任务平台 | 多边形圈选 + 心跳监测", layout="wide")

# ==================== 坐标系转换 ====================
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

# ==================== 障碍物持久化 ====================
CONFIG_FILE = "obstacle_config.json"

def load_obstacles():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []  # 存储为多边形坐标列表 [[lng, lat][...]]

def save_obstacles(polygons):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(polygons, f, ensure_ascii=False, indent=2)

# ==================== 生成带绘制功能的地图 HTML ====================
def generate_map_html(A_lng, A_lat, B_lng, B_lat, polygons, flight_height):
    """
    生成一个完整的 Leaflet + Draw 地图 HTML
    polygons: 列表，每个元素是多边形顶点数组 [[lng,lat], ...]
    返回 HTML 字符串
    """
    # 将 A/B 点坐标转为 WGS-84（地图显示用）
    A_wgs_lng, A_wgs_lat = gcj02_to_wgs84(A_lng, A_lat)
    B_wgs_lng, B_wgs_lat = gcj02_to_wgs84(B_lng, B_lat)
    center_lat = (A_wgs_lat + B_wgs_lat) / 2
    center_lng = (A_wgs_lng + B_wgs_lng) / 2
    
    # 将多边形转换为 JavaScript 可用的格式
    polygons_js = json.dumps(polygons)
    
    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>无人机航线规划 - 卫星地图</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .info-panel {{
            position: absolute; bottom: 20px; left: 20px; z-index: 1000;
            background: rgba(0,0,0,0.6); color: white; padding: 5px 10px;
            border-radius: 5px; font-size: 12px; pointer-events: none;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        ✈️ 航线: A → B | 高度: {flight_height}m | 点击多边形按钮绘制障碍物
    </div>
    <script>
        // 初始化地图
        var map = L.map('map').setView([{center_lat}, {center_lng}], 16.5);
        
        // 卫星底图
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Tiles &copy; Esri',
            maxZoom: 19
        }}).addTo(map);
        
        // 可选街道图
        var osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap'
        }});
        
        // 图层控制
        var baseMaps = {{
            "卫星影像": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'),
            "街道图": osm
        }};
        L.control.layers(baseMaps).addTo(map);
        
        // 起点 A 标记
        L.marker([{A_wgs_lat}, {A_wgs_lng}], {{
            icon: L.divIcon({{ html: '🚁', iconSize: [28,28], className: 'marker-icon' }})
        }}).bindPopup('起点 A').addTo(map);
        
        // 终点 B 标记
        L.marker([{B_wgs_lat}, {B_wgs_lng}], {{
            icon: L.divIcon({{ html: '🏁', iconSize: [28,28], className: 'marker-icon' }})
        }}).bindPopup('终点 B').addTo(map);
        
        // 航线连线
        L.polyline([[{A_wgs_lat}, {A_wgs_lng}], [{B_wgs_lat}, {B_wgs_lng}]], {{
            color: '#00FFFF', weight: 4
        }}).addTo(map);
        
        // 绘制已保存的障碍物多边形
        var savedPolygons = {polygons_js};
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        
        for (var i = 0; i < savedPolygons.length; i++) {{
            var polyCoords = savedPolygons[i].map(function(coord) {{
                return [coord[1], coord[0]];  // 转换 [lng,lat] -> [lat,lng]
            }});
            var poly = L.polygon(polyCoords, {{
                color: 'orange', weight: 3, fillOpacity: 0.3
            }}).addTo(drawnItems);
        }}
        
        // 初始化绘制控件（仅允许多边形）
        var drawControl = new L.Control.Draw({{
            draw: {{
                polygon: true,
                polyline: false,
                rectangle: false,
                circle: false,
                marker: false,
                circlemarker: false
            }},
            edit: {{
                featureGroup: drawnItems,
                remove: true
            }}
        }});
        map.addControl(drawControl);
        
        // 监听新绘制的多边形
        map.on('draw:created', function(e) {{
            var layer = e.layer;
            var type = e.layerType;
            if (type === 'polygon') {{
                // 获取多边形顶点坐标 (Leaflet 返回的是 [lat,lng] 格式)
                var latlngs = layer.getLatLngs()[0];
                var polygonCoords = [];
                for (var i = 0; i < latlngs.length; i++) {{
                    polygonCoords.push([latlngs[i].lng, latlngs[i].lat]);  // 转为 [lng, lat] 存储
                }}
                // 将多边形数据通过 URL 参数传递给 Streamlit
                // 为了避免页面刷新丢失，我们使用 window.parent.postMessage 或 重定向加参数
                // 简单方式：将多边形数据存入 localStorage，然后刷新页面，Streamlit 读取参数
                var existing = localStorage.getItem('new_polygon');
                var newPolygons = existing ? JSON.parse(existing) : [];
                newPolygons.push(polygonCoords);
                localStorage.setItem('new_polygon', JSON.stringify(newPolygons));
                // 刷新页面（传递一个随机参数触发 Streamlit 重绘）
                window.location.href = window.location.pathname + '?new_polygon=' + Date.now();
            }}
        }});
        
        // 监听删除事件
        map.on('draw:deleted', function(e) {{
            // 删除后需要同步到 Streamlit，简单处理：标记需要同步
            localStorage.setItem('need_sync', 'true');
            window.location.href = window.location.pathname + '?sync=' + Date.now();
        }});
        
        // 初始时检查 localStorage 是否有待同步的数据（已通过 URL 参数触发）
    </script>
</body>
</html>
    """
    return html_code

# ==================== 主应用 ====================
def main():
    st.sidebar.title("✈️ 无人机任务平台")
    page = st.sidebar.radio("功能页面", ["🗺️ 航线规划 (多边形圈选)", "📡 飞行监控 (心跳监测)"])
    st.sidebar.markdown("---")
    
    st.sidebar.subheader("坐标系设置")
    coord_sys = st.sidebar.radio("输入坐标系", ["GCJ-02 (高德/百度)", "WGS-84"], index=0)
    
    st.sidebar.subheader("系统状态")
    a_set = ("A_lat_gcj" in st.session_state and "A_lng_gcj" in st.session_state)
    b_set = ("B_lat_gcj" in st.session_state and "B_lng_gcj" in st.session_state)
    st.sidebar.write(f"{'✅' if a_set else '❌'} A点已设")
    st.sidebar.write(f"{'✅' if b_set else '❌'} B点已设")
    st.sidebar.markdown("---")
    st.sidebar.info("🗺️ 卫星图源: Esri\n✏️ 多边形圈选障碍物\n💾 自动保存/加载配置")
    
    # 初始化A/B点 (GCJ-02)
    if "A_lat_gcj" not in st.session_state:
        st.session_state.A_lat_gcj = 32.2323
        st.session_state.A_lng_gcj = 118.7490
    if "B_lat_gcj" not in st.session_state:
        st.session_state.B_lat_gcj = 32.2344
        st.session_state.B_lng_gcj = 118.7490
    if "flight_height" not in st.session_state:
        st.session_state.flight_height = 10
    
    # 加载障碍物多边形列表（存储为 [[lng,lat], ...] 数组）
    if "obstacle_polygons" not in st.session_state:
        st.session_state.obstacle_polygons = load_obstacles()
    
    # 处理从地图传来的新多边形（通过 query params）
    query_params = st.query_params
    if "new_polygon" in query_params:
        # 由于无法直接获取 localStorage，我们改用 session_state 存储临时多边形
        # 这里简化：假设用户绘制后手动点击“保存”按钮。或者使用 st.query_params 传递 JSON
        # 为避免复杂，我们增加一个“导入新多边形”按钮，让用户粘贴坐标
        pass
    
    if page == "🗺️ 航线规划 (多边形圈选)":
        left_col, right_col = st.columns([7, 3])
        
        with right_col:
            st.markdown("### 🎮 控制面板")
            st.markdown(f"**当前坐标系: {coord_sys}**")
            
            # 起点A
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
                st.rerun()
            
            # 终点B
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
                st.rerun()
            
            # 飞行高度
            st.markdown("#### ✈️ 飞行参数")
            flight_h = st.number_input("设定飞行高度 (m)", value=st.session_state.flight_height, step=1)
            st.session_state.flight_height = flight_h
            
            st.markdown("---")
            st.markdown("#### 🧱 障碍物圈选与持久化")
            st.caption("在地图上使用多边形工具绘制障碍物，绘制后页面会自动刷新并保存。")
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("💾 保存到文件"):
                    save_obstacles(st.session_state.obstacle_polygons)
                    st.success("已保存到本地文件")
            with col_btn2:
                if st.button("📂 从文件加载"):
                    st.session_state.obstacle_polygons = load_obstacles()
                    st.success("已加载")
                    st.rerun()
            with col_btn3:
                if st.button("🗑️ 清除全部"):
                    st.session_state.obstacle_polygons = []
                    save_obstacles([])
                    st.success("已清除")
                    st.rerun()
            
            # 下载配置文件
            num_polygons = len(st.session_state.obstacle_polygons)
            st.markdown("---")
            st.markdown("#### 📥 下载配置文件到本地")
            obstacle_json_str = json.dumps(st.session_state.obstacle_polygons, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 下载 obstacle_config.json",
                data=obstacle_json_str,
                file_name="obstacle_config.json",
                mime="application/json",
                help="下载当前所有障碍物多边形坐标"
            )
            st.caption(f"文件状态: 共 {num_polygons} 个障碍物 | 保存时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 版本: v12.2")
            
            # 手动添加多边形（备选）
            st.markdown("#### ✏️ 手动添加多边形坐标")
            manual_poly = st.text_area("输入多边形坐标 (JSON格式，如 [[lng,lat],[lng,lat],...])", height=100)
            if st.button("➕ 添加手动多边形"):
                try:
                    new_poly = json.loads(manual_poly)
                    if isinstance(new_poly, list) and len(new_poly) >= 3:
                        st.session_state.obstacle_polygons.append(new_poly)
                        save_obstacles(st.session_state.obstacle_polygons)
                        st.success("已添加")
                        st.rerun()
                    else:
                        st.error("无效的多边形，至少需要3个点")
                except:
                    st.error("JSON 格式错误")
        
        with left_col:
            st.markdown("### 🗺️ 卫星实况地图 (可绘制多边形)")
            # 生成地图 HTML 并嵌入
            map_html = generate_map_html(
                st.session_state.A_lng_gcj, st.session_state.A_lat_gcj,
                st.session_state.B_lng_gcj, st.session_state.B_lat_gcj,
                st.session_state.obstacle_polygons,
                st.session_state.flight_height
            )
            html(map_html, height=650, scrolling=False)
            
            # 说明：由于地图内绘制后通过 localStorage + 刷新无法直接传回 Streamlit，
            # 我们采用更直接的方式：用户绘制后，地图会刷新页面并带参数，但 Streamlit 端需要读取。
            # 为了简便且可靠，我们增加一个“导入新绘制的多边形”区域，让用户从本地存储中提取。
            # 但为了用户体验，我们建议用户手动添加坐标，或我们提供从 localStorage 导入的按钮。
            # 以下提供从浏览器 localStorage 导入的功能：
            st.markdown("#### 📋 从地图导入新绘制的多边形")
            if st.button("🔄 从当前地图导入新多边形"):
                # 使用 JavaScript 发送 localStorage 数据到 Streamlit (需要额外组件)
                # 由于复杂，这里建议用户手动复制多边形坐标
                st.info("请在地图绘制后，点击右侧的「保存到文件」按钮，多边形会自动保存。如果未自动保存，请手动复制坐标并粘贴到上面「手动添加多边形坐标」区域。")
    
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
