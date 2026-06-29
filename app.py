import streamlit as st
import pandas as pd
import numpy as np
import io

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 语音运营数据智能计算中心 - 4大核心指标看板")
st.markdown("页面已做极致精简，仅呈现 4 项最核心的终极转化率与业务总量，杜绝杂音。")

# 创建上传组件
col1, col2 = st.columns(2)
with col1:
    uploaded_call_file = st.file_uploader("1. 请上传【云总机通话详单】(支持 CSV / XLSX)", type=["csv", "xlsx"])
with col2:
    uploaded_ext_file = st.file_uploader("2. 请上传【分机号】参考表 (支持 CSV / XLSX)", type=["csv", "xlsx"])

def clean_to_int_str(val):
    """数字清洗：将 1912.0 或 '1912' 统一安全地转换为 '1912'"""
    if pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str

# 核心计算逻辑
def process_data(df_call, df_ext):
    df_call.columns = df_call.columns.astype(str).str.strip()
    df_ext.columns = df_ext.columns.astype(str).str.strip()
    
    required_call_cols = ['主叫号码', '通话状态', 'AI通话状态', '人工通话状态', '呼叫时间']
    if any(col not in df_call.columns for col in required_call_cols):
        st.error("❌ 运营数据表中缺少关键列，请检查表头。")
        return None
        
    df_call['主叫号码_clean'] = df_call['主叫号码'].apply(clean_to_int_str)
    df_ext['分机号_clean'] = df_ext['分机号'].apply(clean_to_int_str)
    
    valid_extensions = set(df_ext['分机号_clean'].dropna().unique())
    
    # 1. 计算【房间是否接入】
    df_call['房间是否接入'] = df_call['主叫号码_clean'].apply(
        lambda x: '客房' if (x and x in valid_extensions) else '--'
    )
    
    # 2. 计算【最终成功接通】
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
    
    # 3. 计算【接通方式】
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
    
    # 4 & 5. 计算【呼叫所在日期】和【呼叫所在小时】
    try:
        if pd.api.types.is_numeric_dtype(df_call['呼叫时间']):
            call_time_parsed = pd.to_datetime(df_call['呼叫时间'], unit='D', origin='1899-12-30')
        else:
            call_time_parsed = pd.to_datetime(df_call['呼叫时间'], errors='coerce')
    except Exception:
        call_time_parsed = pd.to_datetime(df_call['呼叫时间'], errors='coerce')

    df_call['呼叫所在日期'] = call_time_parsed.dt.strftime('%Y-%m-%d').fillna('--')
    df_call['呼叫所在小时'] = call_time_parsed.dt.hour.apply(lambda x: str(int(x)) if pd.notna(x) else '--')
    
    df_call = df_call.drop(columns=['主叫号码_clean'])
    return df_call

# --- 网页交互与指标展示 ---
if uploaded_call_file and uploaded_ext_file:
    with st.spinner("正在精准聚合4大核心指标中..."):
        try:
            if uploaded_call_file.name.endswith('.csv'):
                df_call = pd.read_csv(uploaded_call_file)
            else:
                df_call = pd.read_excel(uploaded_call_file)
                
            if uploaded_ext_file.name.endswith('.csv'):
                df_ext = pd.read_csv(uploaded_ext_file)
            else:
                df_ext = pd.read_excel(uploaded_ext_file)
            
            df_result = process_data(df_call, df_ext)
            
            if df_result is not None:
                df_rooms = df_result[df_result['房间是否接入'] == '客房']
                
                # 1. 总来电量
                total_calls = int(len(df_rooms))
                
                # 2. 整体接通率（人工原口径）
                df_rooms['人工通话状态_clean'] = df_rooms['人工通话状态'].astype(str).str.strip()
                man_success_all = int((df_rooms['人工通话状态_clean'] == '接通').sum())
                man_failed_all = int((df_rooms['人工通话状态_clean'] == '未接通').sum())
                man_total_all = man_success_all + man_failed_all
                man_connect_rate_all_str = f"{man_success_all / man_total_all:.2%}" if man_total_all > 0 else "--"
                
                # 3. 上线后人工接通率（新口径）
                connect_types = df_rooms['接通方式'].astype(str).str.strip()
                inc_ai_and_man_success = int((connect_types == '进入AI后，再转接人工，且人工接通').sum())
                direct_man_success = int((connect_types == '直接进入人工，且人工接通').sum())
                online_man_success_volume = inc_ai_and_man_success + direct_man_success
                
                ai_success_man_failed = int((connect_types == 'AI接通，转接人工，人工未接通').sum())
                direct_man_failed = int((connect_types == '直接进入人工且最终未接通').sum())
                online_man_total_volume = ai_success_man_failed + direct_man_failed + inc_ai_and_man_success + direct_man_success
                online_man_connect_rate_str = f"{online_man_success_volume / online_man_total_volume:.2%}" if online_man_total_volume > 0 else "--"
                
                # 4. AI接通率
                df_rooms['AI通话状态_clean'] = df_rooms['AI通话状态'].astype(str).str.strip()
                ai_success_volume = int((df_rooms['AI通话状态_clean'] == '接通').sum())
                ai_total_volume = int(df_rooms['AI通话状态_clean'].isin(['接通', '未接通']).sum())
                ai_connect_rate_str = f"{ai_success_volume / ai_total_volume:.2%}" if ai_total_volume > 0 else "--"
                is_ai_abnormal = (ai_success_volume != ai_total_volume)
                
                # --- 前端渲染（一行四卡片，极度清爽） ---
                st.success("🎉 核心指标聚合成功！")
                
                col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
                
                with col_kpi1:
                    st.metric(label="📞 总来电量", value=f"{total_calls} 次")
                    
                with col_kpi2:
                    if is_ai_abnormal:
                        st.markdown(
                            f"<div style='background-color:#FFD2D2; padding:10px; border-radius:5px; border-left:4px solid #FF0000;'>"
                            f"<p style='margin:0; color:#550000; font-size:14px; font-weight:bold;'>🤖 AI接通率 (⚠️异常)</p>"
                            f"<h3 style='margin:5px 0 0 0; color:#CC0000;'>{ai_connect_rate_str}</h3>"
                            f"</div>", 
                            unsafe_allow_html=True
                        )
                    else:
                        st.metric(label="🤖 AI接通率", value=ai_connect_rate_str)
                        
                with col_kpi3:
                    st.metric(
                        label="🎧 人工接通率", 
                        value=online_man_connect_rate_str,
                        help=f"新精细口径。计算细节：人工接通量({online_man_success_volume}) / 进入人工电话量({online_man_total_volume})"
                    )
                    
                with col_kpi4:
                    st.metric(
                        label="👥 整体接通率 (人工)", 
                        value=man_connect_rate_all_str,
                        help=f"原始口径。计算细节：接通数({man_success_all}) / 有状态总数({man_total_all})"
                    )
                
                st.markdown("---")
                
                # 电子表格导出依然保留完整的审计对账行
                df_summary = pd.DataFrame({
                    "指标名称": ["总来电量", "AI接通率", "人工接通率", "整体接通率（人工）"],
                    "计算结果": [total_calls, ai_connect_rate_str, online_man_connect_rate_str, man_connect_rate_all_str],
                    "口径备注": [
                        "客房呼出总量", 
                        f"AI接通/进入AI {'(⚠️数据不等)' if is_ai_abnormal else '（正常）'}", 
                        f"精确加总口径 (分母包含4种情况)", 
                        "旧有大盘人工接通口径"
                    ]
                })
                
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_summary.to_excel(writer, sheet_name="运营指标看板", index=False)
                    df_result.to_excel(writer, sheet_name="基础明细详单", index=False)
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="📥 下载精简版复盘数据报告",
                    data=excel_data,
                    file_name="语音运营数据简报.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        except Exception as e:
            st.error(f"处理发生非预期错误: {e}")
