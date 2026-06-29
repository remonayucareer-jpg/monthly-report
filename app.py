import streamlit as st
import pandas as pd
import numpy as np
import io

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 语音运营数据智能计算中心")
st.markdown("页面已做极致精简。因【上线前】与【上线后】数据存在时间差，系统已为您开辟**独立计算空间**，避免数据污染。")

# ----------------- 🛠️ 空间分流上传区 -----------------
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
    
    # 判定最终成功接通（指标5分子依赖此逻辑：最终成功接通 == '是'）
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


# ----------------- 📈 核心指标看板渲染 -----------------
if uploaded_post_file and uploaded_ext_file:
    with st.spinner("各时段独立空间指标解耦计算中..."):
        try:
            # 1. 加载分机表
            if uploaded_ext_file.name.endswith('.csv'):
                df_ext = pd.read_csv(uploaded_ext_file)
            else:
                df_ext = pd.read_excel(uploaded_ext_file)
            df_ext.columns = df_ext.columns.astype(str).str.strip()
            df_ext['分机号_clean'] = df_ext['分机号'].apply(clean_to_int_str)
            
            # 2. 算【上线后】的数据
            if uploaded_post_file.name.endswith('.csv'):
                df_post_raw = pd.read_csv(uploaded_post_file)
            else:
                df_post_raw = pd.read_excel(uploaded_post_file)
                
            df_post_res = process_data(df_post_raw, df_ext)
            
            if df_post_res is not None:
                df_rooms_post = df_post_res[df_post_res['房间是否接入'] == '客房']
                
                # 指标 1：总来电量（6个标签组合验证）
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
                
                # 指标 2：AI接通率计算
                df_rooms_post['AI通话状态_clean'] = df_rooms_post['AI通话状态'].astype(str).str.strip()
                ai_success = int((df_rooms_post['AI通话状态_clean'] == '接通').sum())
                ai_total = int(df_rooms_post['AI通话状态_clean'].isin(['接通', '未接通']).sum())
                ai_rate_str = f"{ai_success / ai_total:.2%}" if ai_total > 0 else "--"
                is_ai_abnormal = (ai_success != ai_total)
                
                # 指标 3：上线后人工接通率（新精细口径）
                man_success_post = int((connect_types.isin(['进入AI后，再转接人工，且人工接通', '直接进入人工，且人工接通'])).sum())
                man_total_post = int((connect_types.isin(['进入AI后，再转接人工，且人工接通', '直接进入人工，且人工接通', 'AI接通，转接人工，人工未接通', '直接进入人工且最终未接通'])).sum())
                online_man_rate_str = f"{man_success_post / man_total_post:.2%}" if man_total_post > 0 else "--"
                
                # ⭐新指标 4：上线后整体接通率（人工+AI）
                final_success_count = int((df_rooms_post['最终成功接通'] == '是').sum())
                overall_post_rate_str = f"{final_success_count / total_calls:.2%}" if total_calls > 0 else "--"
                
                # 指标 5：上线前整体接通率（人工原口径）
                pre_man_rate_str = "--"
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
                        pre_man_rate_str = f"{pre_success / pre_total:.2%}" if pre_total > 0 else "--"
                
                # --- 纯净版前端渲染（横向平铺 5 个指标卡片） ---
                st.success("🎉 数据计算完成，以下为精简运营核心看板：")
                
                col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
                
                with col_kpi1:
                    st.metric(label="📞 总来电量 (上线后)", value=f"{total_calls} 次", help="由6个接通场景标签汇总所得")
                    
                with col_kpi2:
                    if is_ai_abnormal:
                        st.markdown(
                            f"<div style='background-color:#FFD2D2; padding:10px; border-radius:5px; border-left:4px solid #FF0000;'>"
                            f"<p style='margin:0; color:#550000; font-size:12px; font-weight:bold;'>🤖 AI接通率 (⚠️异常)</p>"
                            f"<h3 style='margin:5px 0 0 0; color:#CC0000;'>{ai_rate_str}</h3>"
                            f"</div>", 
                            unsafe_allow_html=True
                        )
                    else:
                        st.metric(label="🤖 AI接通率", value=ai_rate_str)
                        
                with col_kpi3:
                    st.metric(label="🎧 人工接通率 (上线后)", value=online_man_rate_str)
                    
                with col_kpi4:
                    st.metric(
                        label="🌐 整体接通率 (人工+AI)", 
                        value=overall_post_rate_str,
                        help=f"计算逻辑：最终成功接通数({final_success_count}) / 6个标签总电量({total_calls})"
                    )
                    
                with col_kpi5:
                    st.metric(
                        label="👥 整体接通率 (上线前人工)", 
                        value=pre_man_rate_str,
                        help="根据历史槽位上传的详单计算所得（旧口径对比参考线）"
                    )
                
                st.markdown("---")
                
                # 导出报表逻辑重组
                df_summary = pd.DataFrame({
                    "指标名称": ["总来电量(上线后)", "AI接通率(上线后)", "人工接通率(上线后)", "整体接通率(人工+AI)", "整体接通率(上线前历史)"],
                    "计算结果": [total_calls, ai_rate_str, online_man_rate_str, overall_post_rate_str, pre_man_rate_str],
                    "公式与时段口径": [
                        "6个核心话务转化标签的总计数", 
                        "AI接通量 / 进入AI电话量", 
                        "人工接通量 / 进入人工电话量", 
                        "最终成功接通('是') / 6个标签总电量",
                        "历史人工接通总数 / 历史人工有状态总数"
                    ]
                })
                
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_summary.to_excel(writer, sheet_name="5大运营核心指标", index=False)
                    df_post_res.to_excel(writer, sheet_name="上线后明细(含最终成功接通)", index=False)
                    if uploaded_pre_file and 'df_pre_res' in locals():
                        df_pre_res.to_excel(writer, sheet_name="上线前历史明细", index=False)
                        
                st.download_button(
                    label="📥 下载5大核心指标对比报告",
                    data=excel_buffer.getvalue(),
                    file_name="语音5大核心指标复盘简报.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        except Exception as e:
            st.error(f"处理发生非预期错误: {e}")
else:
    st.info("💡 提示：请上传分机号参考表和上线后的详单底表。")
