# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
from datetime import datetime

# 页面配置
st.set_page_config(page_title="无人机心跳监测站", layout="wide")
st.title("✈️ 无人机通信心跳监测可视化")
st.markdown("模拟无人机每秒发送心跳包，地面站实时监测并展示序号变化趋势")

# 初始化 session_state 中的数据结构
if "heartbeat_list" not in st.session_state:
    st.session_state.heartbeat_list = []          # 存储心跳记录 [序号, 时间字符串, datetime对象]
if "last_gen_time" not in st.session_state:
    st.session_state.last_gen_time = None         # 上一次生成心跳的时间
if "seq_counter" not in st.session_state:
    st.session_state.seq_counter = 0              # 心跳序号计数器

# 侧边栏控制面板
with st.sidebar:
    st.header("⚙️ 控制面板")
    enable_sending = st.checkbox("🚁 允许无人机发送心跳", value=True)
    if st.button("🗑️ 清空历史数据"):
        st.session_state.heartbeat_list = []
        st.session_state.last_gen_time = None
        st.session_state.seq_counter = 0
        st.success("已清空所有心跳记录")
    st.markdown("---")
    st.info("💡 提示：取消勾选「允许发送」即可模拟无人机掉线，3秒后触发报警")

# 创建用于动态更新的占位容器
status_placeholder = st.empty()
alert_placeholder = st.empty()
chart_placeholder = st.empty()
table_placeholder = st.empty()

# 主循环：模拟心跳生成 + 实时可视化
while True:
    now = datetime.now()
    
    # ----- 模拟无人机发送心跳（每秒一次）-----
    if enable_sending:
        # 判断是否需要生成新心跳（距离上次生成 >= 1秒）
        if (st.session_state.last_gen_time is None or 
            (now - st.session_state.last_gen_time).total_seconds() >= 1):
            
            # 生成新心跳包
            st.session_state.seq_counter += 1
            seq = st.session_state.seq_counter
            time_str = now.strftime("%H:%M:%S")
            heartbeat = [seq, time_str, now]
            st.session_state.heartbeat_list.append(heartbeat)
            st.session_state.last_gen_time = now
            
            # 限制列表长度（保留最近300条，防止内存过大）
            if len(st.session_state.heartbeat_list) > 300:
                st.session_state.heartbeat_list.pop(0)
    
    # ----- 掉线检测 -----
    is_timeout = False
    if st.session_state.heartbeat_list:
        last_heartbeat_time = st.session_state.heartbeat_list[-1][2]
        time_diff = (now - last_heartbeat_time).total_seconds()
        if time_diff > 3:
            is_timeout = True
            alert_msg = f"⚠️ 连接超时！已 {time_diff:.1f} 秒未收到心跳包"
        else:
            alert_msg = f"✅ 连接正常，最后心跳: {time_diff:.1f} 秒前"
    else:
        alert_msg = "⏳ 等待首个心跳包..."
    
    # ----- 更新状态显示 -----
    with status_placeholder.container():
        col1, col2 = st.columns(2)
        if st.session_state.heartbeat_list:
            latest = st.session_state.heartbeat_list[-1]
            col1.metric("最新心跳序号", latest[0])
            col2.metric("最新心跳时间", latest[1])
        else:
            col1.metric("最新心跳序号", "无")
            col2.metric("最新心跳时间", "无")
    
    # ----- 更新报警区域 -----
    if is_timeout:
        alert_placeholder.error(alert_msg)
    else:
        if "等待" in alert_msg:
            alert_placeholder.info(alert_msg)
        else:
            alert_placeholder.success(alert_msg)
    
    # ----- 绘制折线图（序号随时间变化）-----
    if len(st.session_state.heartbeat_list) >= 2:
        # 准备数据
        df = pd.DataFrame(st.session_state.heartbeat_list, 
                         columns=["序号", "时间", "datetime_obj"])
        # 时间列转为字符串（X轴显示）
        df["时间标签"] = df["时间"]
        # 使用 plotly 绘制折线图
        fig = px.line(df, x="时间标签", y="序号", 
                      title="📈 心跳序号变化趋势",
                      labels={"序号": "心跳序号", "时间标签": "接收时间"},
                      markers=True)
        fig.update_layout(height=450)
        chart_placeholder.plotly_chart(fig, use_container_width=True)
    elif len(st.session_state.heartbeat_list) == 1:
        chart_placeholder.info("📊 收集到1个心跳包，继续接收后将显示折线图...")
    else:
        chart_placeholder.info("📊 等待心跳包数据，折线图即将显示...")
    
    # ----- 显示详细数据表格（最近10条）-----
    if st.session_state.heartbeat_list:
        display_df = pd.DataFrame(st.session_state.heartbeat_list[-10:],
                                 columns=["序号", "时间", "datetime_obj"])
        display_df = display_df.drop(columns=["datetime_obj"])
        table_placeholder.dataframe(display_df, use_container_width=True)
    else:
        table_placeholder.info("暂无心跳记录")
    
    # 控制刷新频率（约每秒更新一次页面，保证实时性）
    time.sleep(0.5)
