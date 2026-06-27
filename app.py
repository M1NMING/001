from shapely.geometry import LineString, Point

def plan_route(home, target, obstacles_with_height, fly_height, safety_radius, max_iter=50):
    """
    根据多障碍物生成飞越或绕飞路径。
    obstacles_with_height: [(polygon, height_m), ...]
    fly_height: 当前飞行高度 (m)
    safety_radius: 水平安全缓冲半径 (m)
    max_iter: 最大迭代次数，防止死循环
    """
    # 确定哪些障碍物无法飞越（需要绕飞）
    avoid_obstacles = []
    for poly, h in obstacles_with_height:
        if fly_height <= h + 3:   # 高度不足，必须水平绕飞
            avoid_obstacles.append(poly.buffer(safety_radius))  # 直接存储膨胀后的区域

    if not avoid_obstacles:
        return [home, target]

    path = [home, target]

    for _ in range(max_iter):
        modified = False
        # 遍历当前路径的每一段
        for i in range(len(path) - 1):
            seg = LineString([path[i], path[i+1]])
            for buff in avoid_obstacles:
                if seg.intersects(buff) and not seg.touches(buff):  # 相交且不是仅边界接触
                    # 在障碍物边界上寻找两个绕行点（切线点）
                    boundary = buff.exterior
                    # 将起终点投影到边界上，获取投影距离
                    start_dist = boundary.project(Point(path[i]))
                    end_dist = boundary.project(Point(path[i+1]))

                    # 根据方位选择左侧和右侧绕行点（简单起见，沿边界取两个点）
                    # 这里使用一个偏移量来获取边界两侧的点，实际可根据方向优化
                    offset = boundary.length * 0.1  # 偏移量设为边界的10%
                    p1 = boundary.interpolate((start_dist + offset) % boundary.length)
                    p2 = boundary.interpolate((end_dist - offset) % boundary.length)

                    # 插入新路径点
                    # 插入顺序：... , path[i], p1, p2, path[i+1], ...
                    new_path = path[:i+1] + [(p1.x, p1.y), (p2.x, p2.y)] + path[i+1:]
                    path = new_path
                    modified = True
                    break  # 跳出内层障碍物循环
            if modified:
                break  # 跳出线段循环，从头重新检查新路径

        if not modified:
            break  # 整轮没有修改，所有线段安全
    else:
        print("警告：达到最大迭代次数，路径可能未完全避开所有障碍物")

    return path
