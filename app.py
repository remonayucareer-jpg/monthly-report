import streamlit as st
import pandas as pd
import numpy as np
import io

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 语音运营数据智能计算中心 - Part 2 (多指标看板版)")
st.markdown("上传基础表格后，系统将自动计算**总来电量**及**纯人工接通率**等核心指标，并支持导出多工作表 Excel。")

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

# 核心计算函数
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
    with st.spinner("正在依据模版逻辑精确计算中..."):
        try:
            if uploaded_call_file.name.endswith('.csv'):
                df_call = pd.read_csv(uploaded_call_file)
            else:
                df_call = pd.read_excel(uploaded_call_file)
                
            if uploaded_ext_file.name.endswith('.csv'):
                df_ext = pd.read_csv(uploaded_ext_file)
            else:
                df_ext = pd.read_excel(uploaded_ext_file)
            
            # 获取底表数据
            df_result = process_data(df_call, df_ext)
            
            if df_result is not None:
                st.success("🎉 数据扩充及核心指标计算成功！")
                
                # --- 【核心计算】指标提取 ---
                # 过滤出只有客房接入的数据作为计算基准
                df_rooms = df_result[df_result['房间是否接入'] == '客房']
                
                # 指标 1：总来电量
                total_calls = int(len(df_rooms))
                
                # 新增指标 2：整体接通率（人工）相关计算
                # 严格按照“人工通话状态”这一列的值进行过滤和清洗
                df_rooms['人工通话状态_clean'] = df_rooms['人工通话状态'].astype(str).str.strip()
                
                man_success = int((df_rooms['人工通话状态_clean'] == '接通').sum())
                man_failed = int((df_rooms['人工通话状态_clean'] == '未接通').sum())
                man_total = man_success + man_failed
                
                # 计算接通率（防止分母为 0 导致报错）
                man_connect_rate = man_success / man_total if man_total > 0 else 0.0
                man_connect_rate_str = f"{man_connect_rate:.2%}" if man_total > 0 else "--"
                
                # --- 【前端渲染】运营核心需求指标看板 ---
                st.markdown("## 📈 运营核心需求指标看板")
                
                # 使用 Streamlit 原生卡片并排展示
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1:
                    st.metric(label="📞 总来电量", value=f"{total_calls} 次")
                with m_col2:
                    st.metric(label="👥 整体接通率（人工）", value=man_connect_rate_str, help=f"计算基础：人工接通数({man_success}) / 人工总数({man_total})")
                with m_col3:
                    st.metric(label="📊 人工承接话务量", value=f"{man_total} 次", help=f"包含接通 {man_success} 次，未接通 {man_failed} 次")
                
                st.markdown("---")
                
                # --- 【数据导出】创建指标汇总表，准备写入 Excel 的首页 ---
                df_summary = pd.DataFrame({
                    "核心运营指标名称": [
                        "总来电量（所有启用AI的客房呼出的电话量）", 
                        "整体接通率（人工）"
                    ],
                    "当前计算数值": [
                        total_calls, 
                        man_connect_rate_str
                    ],
                    "计算口径/公式": [
                        "=COUNTIF(详单!房间是否接入, '客房')", 
                        f"人工接通({man_success}) / [人工接通({man_success}) + 人工未接通({man_failed})]"
                    ]
                })
                
                # 在内存中构建多 Sheet 的 XLSX 电子表格
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_summary.to_excel(writer, sheet_name="核心运营报告首页", index=False)
                    df_result.to_excel(writer, sheet_name="云总机通话详单", index=False)
                excel_data = excel_buffer.getvalue()
                
                # 提供高级 XLSX 文件下载
                st.download_button(
                    label="📥 下载完整运营报告 (包含最新人工接通率)",
                    data=excel_data,
                    file_name="语音运营分析复盘报告_v2.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # 预览详单数据
                with st.expander("🔍 点击展开查看底表详单数据预览 (前 5 行)"):
                    all_cols = list(df_result.columns)
                    preview_cols = [c for c in ['酒店名称', '主叫号码', '通话状态', '人工通话状态', '房间是否接入', '最终成功接通', '接通方式'] if c in all_cols]
                    st.dataframe(df_result[preview_cols].head(5), use_container_width=True)
            
        except Exception as e:
            st.error(f"处理发生非预期错误: {e}")
else:
    st.info("💡 提示：请在上方上传表格，系统会自动根据复盘模版生成最新的多指标看板。")
