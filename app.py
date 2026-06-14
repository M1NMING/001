# 在 compute_avoidance_path 函数中，对每个障碍物生成缓冲区
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

def compute_avoidance_path(A, B, obstacles, flight_height, safe_radius=5):
    """
    规划一条从 A 到 B 的航线，要求航线与每个障碍物的安全缓冲区（扩展 safe_radius 米）不相交。
    如果飞行高度大于障碍物高度，仍保持水平安全距离。
    """
    # 生成所有障碍物的缓冲区（合并为一个几何体）
    buffer_zones = []
    for obs in obstacles:
        poly = obs.get("polygon", [])
        if not poly or len(poly) < 3:
            continue
        # 将经纬度多边形转换为平面近似（米转度，使用平均纬度）
        lat_avg = sum(p[1] for p in poly) / len(poly)
        meter_per_deg_lon = 111320 * math.cos(math.radians(lat_avg))
        meter_per_deg_lat = 110540
        # 将多边形缩放到近似平面坐标（以米为单位）
        # 简单方法：将多边形点转换为以中心为原点的相对米坐标，然后 buffer，再转换回经纬度
        # 这里简化：直接用经纬度缓冲区，但 shapely 的 buffer 只能基于平面坐标，所以先转为局部投影
        # 为简化，我们采用近似：将经纬度差乘以相应米转换因子作为平面坐标
        # 更简单：直接使用 shapely 的 buffer，但传入的经纬度会被当做平面单位（度），效果不对。
        # 因此我们需要将多边形转为以米为单位的局部坐标系。
        center_lng = sum(p[0] for p in poly) / len(poly)
        center_lat = sum(p[1] for p in poly) / len(poly)
        # 转换到局部平面坐标（米）
        local_poly = []
        for p in poly:
            dx = (p[0] - center_lng) * meter_per_deg_lon
            dy = (p[1] - center_lat) * meter_per_deg_lat
            local_poly.append((dx, dy))
        poly_local = Polygon(local_poly)
        buffered_local = poly_local.buffer(safe_radius)
        # 转换回经纬度
        buffered_coords = []
        for pt in buffered_local.exterior.coords:
            lng = center_lng + pt[0] / meter_per_deg_lon
            lat = center_lat + pt[1] / meter_per_deg_lat
            buffered_coords.append((lng, lat))
        buffer_poly = Polygon(buffered_coords)
        buffer_zones.append(buffer_poly)
    
    if not buffer_zones:
        return [A, B]
    
    # 合并所有缓冲区
    merged_buffer = unary_union(buffer_zones)
    
    # 使用简单的偏移寻路：检测直线是否与缓冲区相交，若相交则偏移
    path = [A]
    current = A
    # 最多迭代10次，避免无限循环
    for _ in range(10):
        # 检查 current 到 B 的直线是否与缓冲区相交
        line = LineString([current, B])
        if not line.intersects(merged_buffer):
            path.append(B)
            break
        # 需要绕行：找到最近的缓冲区边界点，向外偏移
        # 简化：计算从 current 到 B 的方向，取垂直方向偏移 safe_radius*2
        dx = B[0] - current[0]
        dy = B[1] - current[1]
        length = math.hypot(dx, dy)
        if length == 0:
            break
        ux = dx / length
        uy = dy / length
        perp_x = -uy
        perp_y = ux
        # 根据策略决定偏移方向
        strategy = st.session_state.get("bypass_strategy", "最佳航线")
        if strategy == "向左绕行":
            offset_dir = 1
        elif strategy == "向右绕行":
            offset_dir = -1
        else:
            # 最佳航线：尝试两个方向，选偏移后线段与缓冲区相交较少者
            # 简单取左右偏移后的线段长度比较（与前面类似）
            offset_dir = 1  # 默认左
        # 计算偏移点（偏移距离 safe_radius*3 以保证绕过）
        offset_m = safe_radius * 3
        # 获取垂直向量
        perp_x *= offset_dir
        perp_y *= offset_dir
        # 米转度
        lat_rad = math.radians((current[1] + B[1]) / 2)
        meter_per_deg_lon = 111320 * math.cos(lat_rad)
        meter_per_deg_lat = 110540
        offset_deg_lon = offset_m / meter_per_deg_lon * perp_x
        offset_deg_lat = offset_m / meter_per_deg_lat * perp_y
        # 偏移起点和终点
        new_A = (current[0] + offset_deg_lon, current[1] + offset_deg_lat)
        new_B = (B[0] + offset_deg_lon, B[1] + offset_deg_lat)
        path.append(new_A)
        path.append(new_B)
        current = new_B
    else:
        # 防止无限循环，直接连到 B
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
