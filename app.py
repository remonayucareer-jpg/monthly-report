import streamlit as st
import pandas as pd
import numpy as np
import io

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 南京金鹰世界G酒店-语音运营数据分析")
st.markdown("页面已完成样式与话术的 1:1 深度复刻，完美对接试用期复盘报告结构。")

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
    """数字清洗：将 1912.0 或 '1912' 统一安全地转换为 '1912'"""
    if pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str


# 核心数据清洗计算引擎
def process_data(df_call, df_ext):
    df_call.columns = df_call.columns.astype(str).str.strip()
    
    required_call_cols = ['主叫号码', '通话状态', 'AI通话状态', '人工通话状态']
    if any(col not in df_call.columns for col in required_call_cols):
        return None
        
    df_call['主叫号码_clean'] = df_call['主叫号码'].apply(clean_to_int_str)
    valid_extensions = set(df_ext['分机号_clean'].dropna().unique())
    
    # 判定客房接入
    df_call['房间是否接入'] = df_call['主叫号码_clean'].apply(
        lambda x: '客房' if (x and x in valid_extensions) else '--'
    )
    
    # 判定最终成功接通
    def check_final_success(row):
        if row['房间是否接入'] != '客房':
            return '--'
        m = str(row['通话状态']).strip() if pd.notna(row['通话状态']) else '--'
        n = str(row['AI通话状态']).strip() if pd.notna(row['AI通话状态']) else '--'
        o = str(row['人工通话状态']).strip() if pd.notna(row['人工通话状态']) else '--'
        if (m == '接通' and n == '接通' and o == '接通') or \
           (m == '接通' and n == '接通' and o == '--') or \
           (m == '接通' and n == '--' and o == '接通'):
            return '是'
        return '否'
    df_call['最终成功接通'] = df_call.apply(check_final_success, axis=1)
    
    # 判定接通方式（6个基本标签划分）
    def check_connect_type(row):
        if row['房间是否接入'] != '客房':
            return '--'
        m = str(row['通话状态']).strip() if pd.notna(row['通话状态']) else '--'
        n = str(row['AI通话状态']).strip() if pd.notna(row['AI通话状态']) else '--'
        o = str(row['人工通话状态']).strip() if pd.notna(row['人工通话状态']) else '--'
        
        if m == '接通' and n == '接通' and o == '接通':
            return '进入AI后，再转接人工，且人工接通'
        elif m == '接通' and n == '接通' and o == '未接通':
            return 'AI接通，转接人工，人工未接通'
        elif m == '接通' and n == '接通' and o == '--':
            return '进入AI后，AI直接完成，未转接人工'
        elif m == '接通' and n == '--' and o == '接通':
            return '直接进入人工，且人工接通'
        elif m == '未接通' and n == '--' and o == '--':
            return '客人主动挂断'
        elif m == '未接通' and n == '--' and o == '未接通':
            return '直接进入人工且最终未接通'
        else:
            return '异常'
            
    df_call['接通方式'] = df_call.apply(check_connect_type, axis=1)
    df_call = df_call.drop(columns=['主叫号码_clean'])
    return df_call


# ----------------- 📈 1:1 看板数据渲染 -----------------
if uploaded_post_file and uploaded_ext_file:
    with st.spinner("双时段效益多维对账中..."):
        try:
            # 1. 加载分机表
            if uploaded_ext_file.name.endswith('.csv'):
                df_ext = pd.read_csv(uploaded_ext_file)
            else:
                df_ext = pd.read_excel(uploaded_ext_file)
            df_ext.columns = df_ext.columns.astype(str).str.strip()
            df_ext['分机号_clean'] = df_ext['分机号'].apply(clean_to_int_str)
            
            # 2. 计算【上线后】时段数据
            if uploaded_post_file.name.endswith('.csv'):
                df_post_raw = pd.read_csv(uploaded_post_file)
            else:
                df_post_raw = pd.read_excel(uploaded_post_file)
                
            df_post_res = process_data(df_post_raw, df_ext)
            
            if df_post_res is not None:
                df_rooms_post = df_post_res[df_post_res['房间是否接入'] == '客房']
                
                # 总来电量
                connect_types = df_rooms_post['接通方式'].astype(str).str.strip()
                valid_tags = [
                    '进入AI后，AI直接完成，未转接人工', 
                    'AI接通，转接人工，人工未接通', 
                    '直接进入人工且最终未接通', 
                    '进入AI后，再转接人工，且人工接通', 
                    '直接进入人工，且人工接通', 
                    '客人主动挂断'
                ]
                total_calls = int(connect_types.isin(valid_tags).sum())
                
                # AI接通率
                df_rooms_post['AI通话状态_clean'] = df_rooms_post['AI通话状态'].astype(str).str.strip()
                ai_success = int((df_rooms_post['AI通话状态_clean'] == '接通').sum())
                ai_total = int(df_rooms_post['AI通话状态_clean'].isin(['接通', '未接通']).sum())
                ai_rate_str = f"{ai_success / ai_total:.1%}" if ai_total > 0 else "--"
                is_ai_abnormal = (ai_success != ai_total)
                
                # 人工接通率
                man_success_post = int((connect_types.isin(['进入AI后，再转接人工，且人工接通', '直接进入人工，且人工接通'])).sum())
                man_total_post = int((connect_types.isin(['进入AI后，再转接人工，且人工接通', '直接进入人工，且人工接通', 'AI接通，转接人工，人工未接通', '直接进入人工且最终未接通'])).sum())
                online_man_rate_str = f"{man_success_post / man_total_post:.1%}" if man_total_post > 0 else "--"
                
                # 整体接通率（人工+AI）
                final_success_count = int((df_rooms_post['最终成功接通'] == '是').sum())
                overall_post_rate = final_success_count / total_calls if total_calls > 0 else 0.0
                overall_post_rate_str = f"{overall_post_rate:.1%}" if total_calls > 0 else "--"
                
                # 跨空间指标初始化
                pre_man_rate_str = "--"
                lift_rate_str = "--"
                saved_calls_str = "--"
                lift_value = None
                
                if uploaded_pre_file:
                    if uploaded_pre_file.name.endswith('.csv'):
                        df_pre_raw = pd.read_csv(uploaded_pre_file)
                    else:
                        df_pre_raw = pd.read_excel(uploaded_pre_file)
                        
                    df_pre_res = process_data(df_pre_raw, df_ext)
                    if df_pre_res is not None:
                        df_rooms_pre = df_pre_res[df_pre_res['房间是否接入'] == '客房']
                        df_rooms_pre['人工通话状态_clean'] = df_rooms_pre['人工通话状态'].astype(str).str.strip()
                        pre_success = int((df_rooms_pre['人工通话状态_clean'] == '接通').sum())
                        pre_failed = int((df_rooms_pre['人工通话状态_clean'] == '未接通').sum())
                        pre_total = pre_success + pre_failed
                        
                        if pre_total > 0:
                            overall_pre_rate = pre_success / pre_total
                            pre_man_rate_str = f"{overall_pre_rate:.1%}"
                            
                            # 整体接通率提升
                            lift_value = overall_post_rate - overall_pre_rate
                            lift_rate_str = f"{lift_value:.1%}"
                            
                            # 减少电话漏接量 (四舍五入)
                            saved_calls = int(round(total_calls * lift_value))
                            saved_calls_str = f"{saved_calls}.0"
                
                # --- 🎛️ PART 1：1比1复刻报表看板呈现 ---
                st.markdown("### 📞 PART1：酒店电话数据")
                
                # 顶部小字：总来电量大字标签
                st.info(f"**总来电量（所有启用AI的客房呼出的电话量）：{total_calls}**")
                
                st.markdown("#### **电话接通率情况**")
                
                # 1:1 复刻双层表头式排版逻辑
                col_b1, col_b2, col_b3, col_b4, col_b5, col_b6 = st.columns(6)
                
                with col_b1:
                    st.metric(label="上线前整体接通率（人工）", value=pre_man_rate_str)
                with col_b2:
                    st.metric(label="上线后人工接通率", value=online_man_rate_str)
                with col_b3:
                    if is_ai_abnormal:
                        st.markdown(
                            f"<div style='background-color:#FFD2D2; padding:5px; border-radius:5px; border-left:3px solid #FF0000;'>"
                            f"<p style='margin:0; color:#550000; font-size:14px;'>AI接通率</p>"
                            f"<h3 style='margin:5px 0 0 0; color:#CC0000;'>{ai_rate_str}</h3>"
                            f"</div>", 
                            unsafe_allow_html=True
                        )
                    else:
                        st.metric(label="AI接通率", value=ai_rate_str)
                with col_b4:
                    st.metric(label="上线后整体接通率（人工+AI）", value=overall_post_rate_str)
                with col_b5:
                    st.metric(label="整体接通率提升", value=lift_rate_str)
                with col_b6:
                    st.metric(label="减少电话漏接量", value=saved_calls_str)
                
                st.markdown("---")
                
                # 汇总报表导出字典
                df_summary = pd.DataFrame({
                    "表格槽位": ["总来电量", "整体接通率（人工）[上线前]", "人工接通率[上线后]", "AI接通率[上线后]", "整体接通率（人工+AI）[上线后]", "整体接通率提升", "减少电话漏接量"],
                    "复盘数值结果": [total_calls, pre_man_rate_str, online_man_rate_str, ai_rate_str, overall_post_rate_str, lift_rate_str, saved_calls_str],
                    "系统核账备注": ["客房启用标签汇总数", "历史纯人工接通表现", "进入人工通道后接通率", "AI接听响应表现", "大盘综合接通能力", "改造后拉升净值", "挽回的客对话服务量"]
                })
                
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_summary.to_excel(writer, sheet_name="复盘报告1比1对照表", index=False)
                    df_post_res.to_excel(writer, sheet_name="上线后清洗详单", index=False)
                    if uploaded_pre_file and 'df_pre_res' in locals():
                        df_pre_res.to_excel(writer, sheet_name="上线前清洗详单", index=False)
                        
                st.download_button(
                    label="📥 导出 1:1 复盘报告对照 Excel",
                    data=excel_buffer.getvalue(),
                    file_name="南京金鹰世界G酒店_复盘报告数据.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        except Exception as e:
            st.error(f"分析处理发生非预期异常: {e}")
else:
    st.info("💡 提示：请先在上方数据中心上传分机配置参考表与上线后详单底表。")
