import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 南京金鹰世界G酒店-语音运营数据分析")
st.markdown("页面已完成【网页呈现过程、Excel 仅留结果】的双轨数据流重构，确保对账透明与导出的专业性。")

# ----------------- 🛠️ 数据矩阵上传区 -----------------
st.markdown("### 📥 数据矩阵上传中心")
col_up1, col_up2, col_up3 = st.columns(3)

with col_up1:
    st.markdown("**▼ 基础配置表**")
    uploaded_ext_file = st.file_uploader("分机号参考表 (CSV/XLSX)", type=["csv", "xlsx"], key="ext")

with col_up2:
    st.markdown("**▼ 空间 A：上线后运营时段**")
    uploaded_post_file = st.file_uploader("上线后-云总机通话详单", type=["csv", "xlsx"], key="post")

with col_up3:
    st.markdown("**▼ 空间 B：上线前历史时段**")
    uploaded_pre_file = st.file_uploader("上线前-历史通话详单 (选填)", type=["csv", "xlsx"], key="pre")


def clean_to_int_str(val):
    if pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str


def extract_hour_from_datetime(val):
    """从标准呼叫时间字符串中精准切出小时"""
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    match = re.search(r'(\d{1,2}):\d{2}:\d{2}', val_str)
    if match:
        try:
            h = int(match.group(1))
            if 0 <= h <= 23:
                return h
        except:
            pass
    return None


# 统一的数据清洗计算引擎
def process_data(df_raw, df_ext):
    df_call = df_raw.copy()
    df_call.columns = df_call.columns.astype(str).str.strip()
    
    required_cols = ['主叫号码', '通话状态', 'AI通话状态', '人工通话状态', '呼叫时间']
    if any(col not in df_call.columns for col in required_cols):
        return None
        
    df_call['主叫号码_clean'] = df_call['主叫号码'].apply(clean_to_int_str)
    valid_extensions = set(df_ext['分机号_clean'].dropna().unique())
    
    # 1. 判定客房接入
    df_call['房间是否接入'] = df_call['主叫号码_clean'].apply(
        lambda x: '客房' if (x and x in valid_extensions) else '--'
    )
    
    # 2. 从“呼叫时间”解析标准小时
    df_call['⚡标准时段'] = df_call['呼叫时间'].apply(extract_hour_from_datetime)

    # 3. 判定最终成功接通
    def check_final_success(row):
        if row['房间是否接入'] != '客房': 
            return '--'
        m = str(row['通话状态']).strip()
        n = str(row['AI通话状态']).strip()
        o = str(row['人工通话状态']).strip()
        if m == '接通' or n == '接通' or o == '接通':
            return '是'
        return '否'
    df_call['最終成功接通'] = df_call.apply(check_final_success, axis=1)
    
    # 4. 判定接通方式划分
    def check_connect_type(row):
        if row['房间是否接入'] != '客房': 
            return '--'
        m = str(row['通话状态']).strip()
        n = str(row['AI通话状态']).strip()
        o = str(row['人工通话状态']).strip()
        
        if m == '接通' and n == '接通' and o == '接通':
            return '进入AI后，再转接人工，且人工接通'
        elif m == '接通' and n == '接通' and o == '未接通':
            return 'AI接通，转接人工，人工未接通'
        elif m == '接通' and n == '接通' and (o == '--' or o == ''):
            return '进入AI后，AI直接完成，未转接人工'
        elif m == '接通' and (n == '--' or n == '') and o == '接通':
            return '直接进入人工，且人工接通'
        elif m == '未接通' and (n == '--' or n == '') and (o == '--' or o == ''):
            return '客人主动挂断'
        elif m == '未接通' and (n == '--' or n == '') and o == '未接通':
            return '直接进入人工且最终未接通'
        elif m == '接通' and (n == '--' or n == '') and (o == '--' or o == ''):
            return '直接进入人工，且人工接通'
        else:
            return '其他未划分场景'
            
    df_call['接通方式'] = df_call.apply(check_connect_type, axis=1)
    return df_call


# ----------------- 📈 看板数据渲染 -----------------
if uploaded_post_file and uploaded_ext_file:
    with st.spinner("双时段效益及24H时段多维对账中..."):
        try:
            # 加载分机参考表
            if uploaded_ext_file.name.endswith('.csv'):
                df_ext = pd.read_csv(uploaded_ext_file)
            else:
                df_ext = pd.read_excel(uploaded_ext_file)
            df_ext.columns = df_ext.columns.astype(str).str.strip()
            df_ext['分机号_clean'] = df_ext['分机号'].apply(clean_to_int_str)
            
            # 加载上线后表格
            if uploaded_post_file.name.endswith('.csv'):
                df_post_raw = pd.read_csv(uploaded_post_file)
            else:
                df_post_raw = pd.read_excel(uploaded_post_file)
                
            df_post_res = process_data(df_post_raw, df_ext)
            
            if df_post_res is not None:
                df_rooms_post = df_post_res[df_post_res['房间是否接入'] == '客房']
                total_calls = len(df_rooms_post)
                
                # 大盘指标计算
                df_rooms_post['AI通话状态_clean'] = df_rooms_post['AI通话状态'].astype(str).str.strip()
                ai_success = int((df_rooms_post['AI通话状态_clean'] == '接通').sum())
                ai_total = int(df_rooms_post['AI通话状态_clean'].isin(['接通', '未接通']).sum())
                ai_rate_str = f"{ai_success / ai_total:.1%}" if ai_total > 0 else "--"
                is_ai_abnormal = (ai_success != ai_total) if ai_total > 0 else False
                
                connect_types = df_rooms_post['接通方式'].str.strip()
                man_success_post = int(connect_types.isin(['进入AI后，再转接人工，且人工接通', '直接进入人工，且人工接通']).sum())
                man_total_post = int(connect_types.isin(['进入AI后，再转接人工，且人工接通', '直接进入人工，且人工接通', 'AI接通，转接人工，人工未接通', '直接进入人工且最终未接通']).sum())
                online_man_rate_str = f"{man_success_post / man_total_post:.1%}" if man_total_post > 0 else "--"
                
                final_success_count = int((df_rooms_post['最終成功接通'] == '是').sum())
                overall_post_rate = final_success_count / total_calls if total_calls > 0 else 0.0
                overall_post_rate_str = f"{overall_post_rate:.1%}" if total_calls > 0 else "--"
                
                pre_man_rate_str = "--"
                lift_rate_str = "--"
                saved_calls_str = "--"
                
                # 初始化分时数据大盘（双轨制承载容器）
                hours_range = list(range(24))
                df_web_display = pd.DataFrame({"时段": [f"{i}:00" for i in hours_range], "⚡H_int": hours_range})
                df_excel_export = pd.DataFrame({"时段": [f"{i}:00" for i in hours_range], "⚡H_int": hours_range})
                
                # 上线后分时放量聚合
                df_h_post = df_rooms_post[df_rooms_post['⚡标准时段'].notna()]
                post_h_total = df_h_post.groupby('⚡标准时段').size()
                post_h_success = df_h_post[df_h_post['最終成功接通'] == '是'].groupby('⚡标准时段').size()
                
                # 计算上线前历史数据
                pre_h_total, pre_h_success = {}, {}
                if uploaded_pre_file:
                    if uploaded_pre_file.name.endswith('.csv'):
                        df_pre_raw = pd.read_csv(uploaded_pre_file)
                    else:
                        df_pre_raw = pd.read_excel(uploaded_pre_file)
                        
                    df_pre_res = process_data(df_pre_raw, df_ext)
                    if df_pre_res is not None:
                        df_rooms_pre = df_pre_res[df_pre_res['房间是否接入'] == '客房']
                        
                        pre_success = int((df_rooms_pre['最終成功接通'] == '是').sum())
                        pre_total = len(df_rooms_pre)
                        
                        if pre_total > 0:
                            overall_pre_rate = pre_success / pre_total
                            pre_man_rate_str = f"{overall_pre_rate:.1%}"
                            lift_value = overall_post_rate - overall_pre_rate
                            lift_rate_str = f"{lift_value:.1%}"
                            saved_calls_str = f"{int(round(total_calls * lift_value))}.0"
                        
                        # 上线前分时聚合
                        df_h_pre = df_rooms_pre[df_rooms_pre['⚡标准时段'].notna()]
                        pre_h_total = df_h_pre.groupby('⚡标准时段').size()
                        pre_h_success = df_h_pre[df_h_pre['最終成功接通'] == '是'].groupby('⚡标准时段').size()
                
                # 核心：执行双轨数据隔离计算
                def generate_dual_track_data(row):
                    h = row['⚡H_int']
                    
                    # 抓取上线前、上线后各时段的绝对分子分母
                    cnt_pre_tot = pre_h_total.get(h, 0)
                    cnt_pre_suc = pre_h_success.get(h, 0)
                    cnt_post_tot = post_h_total.get(h, 0)
                    cnt_post_suc = post_h_success.get(h, 0)
                    
                    # 转换为浮点比率
                    val_pre = cnt_pre_suc / cnt_pre_tot if cnt_pre_tot > 0 else None
                    val_post = cnt_post_suc / cnt_post_tot if cnt_post_tot > 0 else None
                    
                    # --- TRACK 1：构建网页端带过程描述的字符串 ---
                    web_pre = f"{val_pre:.1%} ({cnt_pre_suc}/{cnt_pre_tot})" if val_pre is not None else "--"
                    web_post = f"{val_post:.1%} ({cnt_post_suc}/{cnt_post_tot})" if val_post is not None else "--"
                    
                    if val_pre is not None and val_post is not None:
                        diff = val_post - val_pre
                        if diff > 0:
                            web_lift = f"↑ {diff:.1%} ({val_post:.1%} - {val_pre:.1%})"
                        elif diff < 0:
                            web_lift = f"{diff:.1%} ({val_post:.1%} - {val_pre:.1%}) ↓"
                        else:
                            web_lift = f"0.0% ({val_post:.1%} - {val_pre:.1%})"
                    else:
                        web_lift = "--"
                        
                    # --- TRACK 2：构建 Excel 纯净结果数值形式 ---
                    excel_pre = f"{val_pre:.1%}" if val_pre is not None else "--"
                    excel_post = f"{val_post:.1%}" if val_post is not None else "--"
                    excel_lift = f"{val_post - val_pre:.1%}" if (val_pre is not None and val_post is not None) else "--"
                    
                    return pd.Series([web_pre, web_post, web_lift, excel_pre, excel_post, excel_lift])
                
                # 填充映射
                target_cols = [
                    'web_pre', 'web_post', 'web_lift',
                    'excel_pre', 'excel_post', 'excel_lift'
                ]
                df_web_display[target_cols] = df_web_display.apply(generate_dual_track_data, axis=1)
                df_excel_export[target_cols] = df_web_display[target_cols] # 复用计算结果
                
                # 格式归一化清洗
                # 网页版定型：
                df_web_final = pd.DataFrame({
                    "时段": df_web_display["时段"],
                    "整体接通率（人工）[上线前]": df_web_display["web_pre"],
                    "整体接通率（人工+AI）[上线后]": df_web_display["web_post"],
                    "整体接通率提升（上线后）": df_web_display["web_lift"]
                })
                
                # Excel 导出版定型（纯净结果）：
                df_excel_final = pd.DataFrame({
                    "时段": df_excel_export["时段"],
                    "整体接通率（人工）[上线前]": df_excel_export["excel_pre"],
                    "整体接通率（人工+AI）[上线后]": df_excel_export["excel_post"],
                    "整体接通率提升（上线后）": df_excel_export["excel_lift"]
                })
                
                # --- 前端面板渲染 ---
                st.markdown("### 📞 PART1：酒店电话数据")
                st.info(f"**总来电量（所有启用AI的客房呼出的电话量）：{total_calls}**")
                
                st.markdown("#### **电话接通率情况**")
                col_b1, col_b2, col_b3, col_b4, col_b5, col_b6 = st.columns(6)
                with col_b1: st.metric(label="上线前整体接通率（人工）", value=pre_man_rate_str)
                with col_b2: st.metric(label="上线后人工接通率", value=online_man_rate_str)
                with col_b3:
                    if is_ai_abnormal:
                        st.markdown(f"<div style='background-color:#FFD2D2; padding:5px; border-radius:5px; border-left:3px solid #FF0000;'><p style='margin:0; color:#550000; font-size:14px;'>AI接通率</p><h3 style='margin:5px 0 0 0; color:#CC0000;'>{ai_rate_str}</h3></div>", unsafe_allow_html=True)
                    else:
                        st.metric(label="AI接通率", value=ai_rate_str)
                with col_b4: st.metric(label="上线后整体接通率（人工+AI）", value=overall_post_rate_str)
                with col_b5: st.metric(label="整体接通率提升", value=lift_rate_str)
                with col_b6: st.metric(label="减少电话漏接量", value=saved_calls_str)
                
                st.markdown("---")
                st.markdown("#### ⏰ 24小时分时段接通率精细分析情况 (网页端：呈现完整推导过程)")
                st.dataframe(df_web_final, use_container_width=True)
                
                # 构建纯净结果的 Excel 导出文件
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_excel_final.to_excel(writer, sheet_name="24小时分时段看板(仅结果)", index=False)
                    df_post_res.to_excel(writer, sheet_name="上线后明细详单", index=False)
                    if uploaded_pre_file and 'df_pre_res' in locals():
                        df_pre_res.to_excel(writer, sheet_name="上线前明细详单", index=False)
                        
                st.download_button(
                    label="📥 导出带24小时分时分析的全量 Excel (纯净结果版)",
                    data=excel_buffer.getvalue(),
                    file_name="南京金鹰世界G酒店_时段复盘全量报告.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("❌ 详单解析失败，请检查基础列名是否完全吻合。")
        except Exception as e:
            st.error(f"分析处理发生非预期异常: {e}")
else:
    st.info("💡 提示：请先在上方数据中心上传分机配置参考表与上线后详单底表。")
