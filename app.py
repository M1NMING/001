def compute_avoidance_path(A, B, obstacles, flight_height, safe_radius, strategy):
    if not obstacles:
        return [A, B]
    # 筛选活跃障碍物
    active_obstacles = []
    for obs in obstacles:
        poly = obs.get("polygon", [])
        height = obs.get("height", 10.0)
        if poly and len(poly) >= 3 and flight_height <= height:
            active_obstacles.append(obs)
    if not active_obstacles:
        return [A, B]
    ref_point = ((A[0]+B[0])/2, (A[1]+B[1])/2)
    buffer_zones = []
    for obs in active_obstacles:
        poly = obs.get("polygon", [])
        buf = get_buffer_polygon(poly, safe_radius, ref_point)
        buffer_zones.append(buf if buf else poly)
    path = [A]
    current_t = 0.0
    for idx, obs in enumerate(active_obstacles):
        poly = obs.get("polygon", [])
        intersections = get_line_polygon_intersection_points(A, B, poly)
        if not intersections:
            continue
        t_values = []
        dist_AB = distance_meters(A, B)
        if dist_AB < 1e-8:
            continue
        for pt in intersections:
            t = distance_meters(A, pt) / dist_AB
            t_values.append(t)
        if not t_values:
            continue
        t_enter = min(t_values)
        t_exit = max(t_values)
        if t_exit <= current_t:
            continue
        margin = safe_radius / dist_AB * 1.5
        t_start = max(current_t, t_enter - margin)
        t_end = min(1.0, t_exit + margin)
        if t_end - t_start < 0.01:
            t_start = max(current_t, t_enter - 0.03)
            t_end = min(1.0, t_exit + 0.03)
        P_start = interpolate_point_on_line(A, B, t_start)
        P_end = interpolate_point_on_line(A, B, t_end)
        if distance_meters(path[-1], P_start) > 0.1:
            path.append(P_start)
        buffer_poly = buffer_zones[idx]
        if not buffer_poly:
            path.append(P_end)
            current_t = t_end
            continue
        # 将入点和出点投影到缓冲区边界上
        start_on_buf, start_dist = point_on_polygon_boundary(P_start, buffer_poly)
        end_on_buf, end_dist = point_on_polygon_boundary(P_end, buffer_poly)
        ring = LinearRing(buffer_poly)
        total_len = ring.length
        # 计算顺时针和逆时针距离
        if end_dist >= start_dist:
            dist_cw = end_dist - start_dist
            dist_ccw = total_len - dist_cw
        else:
            dist_ccw = start_dist - end_dist
            dist_cw = total_len - dist_ccw
        # 左右方向修正：向左绕行 -> 顺时针（原为逆时针），向右绕行 -> 逆时针
        if strategy == "向左绕行":
            use_cw = True
        elif strategy == "向右绕行":
            use_cw = False
        else:  # 最佳航线
            use_cw = dist_cw <= dist_ccw
        # 生成边界路径
        if use_cw:
            if end_dist >= start_dist:
                segment = substring(ring, start_dist, end_dist)
            else:
                segment = substring(ring, start_dist, total_len)
                if end_dist > 0:
                    seg2 = substring(ring, 0, end_dist)
                    segment = LineString(list(segment.coords) + list(seg2.coords))
        else:
            # 逆时针：取从end到start的顺时针段并反转
            if start_dist >= end_dist:
                seg = substring(ring, end_dist, start_dist)
            else:
                seg1 = substring(ring, end_dist, total_len)
                seg2 = substring(ring, 0, start_dist)
                seg = LineString(list(seg1.coords) + list(seg2.coords))
            segment = LineString(list(seg.coords)[::-1])
        boundary_points = list(segment.coords)
        # 确保顺序从start到end
        if len(boundary_points) > 1:
            if distance_meters(boundary_points[0], start_on_buf) > distance_meters(boundary_points[-1], start_on_buf):
                boundary_points = boundary_points[::-1]
            for pt in boundary_points:
                if distance_meters(path[-1], pt) > 0.1:
                    path.append(pt)
        if distance_meters(path[-1], P_end) > 0.1:
            path.append(P_end)
        current_t = t_end
    if distance_meters(path[-1], B) > 1e-6:
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
    return simplified
