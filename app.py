import streamlit as st
import pandas as pd
import numpy as np

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 语音运营数据智能计算中心 - Part 1 (模版完美对齐版)")
st.markdown("请在下方上传您的**运营数据**和**分机号表**，系统将严格按照您的 Excel 模版公式完成 5 行数据扩充。")

# 创建上传组件
col1, col2 = st.columns(2)
with col1:
    uploaded_call_file = st.file_uploader("1. 请上传【云总机通话详单】(支持 CSV / XLSX)", type=["csv", "xlsx"])
with col2:
    uploaded_ext_file = st.file_uploader("2. 请上传【分机号】参考表 (支持 CSV / XLSX)", type=["csv", "xlsx"])

def clean_to_int_str(val):
    """极其严格的数字清洗：将 1912.0 或 '1912' 统一安全地转换为 '1912'"""
    if pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str

# 核心计算函数
def process_data(df_call, df_ext):
    # 清洗表头空格
    df_call.columns = df_call.columns.astype(str).str.strip()
    df_ext.columns = df_ext.columns.astype(str).str.strip()
    
    # 检查必要的关键列
    required_call_cols = ['主叫号码', '通话状态', 'AI通话状态', '人工通话状态', '呼叫时间']
    missing_call_cols = [col for col in required_call_cols if col not in df_call.columns]
    
    if missing_call_cols:
        st.error(f"❌ 运营数据表中缺少以下关键列，请检查表头是否一致：{missing_call_cols}")
        return None
        
    if '分机号' not in df_ext.columns:
        st.error("❌ 分机号参考表中缺少【分机号】列，请检查表头。")
        return None

    # 统一转换主叫号码和分机号为干净的纯数字字符串
    df_call['主叫号码_clean'] = df_call['主叫号码'].apply(clean_to_int_str)
    df_ext['分机号_clean'] = df_ext['分机号'].apply(clean_to_int_str)
    
    # 获取有效的分机号集合
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
        
        cond1 = (m == '接通' and n == '接通' and o == '接通')
        cond2 = (m == '接通' and n == '接通' and o == '--')
        cond3 = (m == '接通' and n == '--' and o == '接通')
        
        if cond1 or cond2 or cond3:
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
    # 采用更强大的日期转换机制，自动兼容 Excel 序列号及标准字符串
    try:
        # 如果是 Excel 序列号数字，先转换为标准日期
        if pd.api.types.is_numeric_dtype(df_call['呼叫时间']):
            call_time_parsed = pd.to_datetime(df_call['呼叫时间'], unit='D', origin='1899-12-30')
        else:
            # 尝试正常字符串转换
            call_time_parsed = pd.to_datetime(df_call['呼叫时间'], errors='coerce')
    except Exception:
        call_time_parsed = pd.to_datetime(df_call['呼叫时间'], errors='coerce')

    df_call['呼叫所在日期'] = call_time_parsed.dt.strftime('%Y-%m-%d').fillna('--')
    df_call['呼叫所在小时'] = call_time_parsed.dt.hour.apply(
        lambda x: str(int(x)) if pd.notna(x) else '--'
    )
    
    # 移除辅助清洗列
    df_call = df_call.drop(columns=['主叫号码_clean'])
    
    return df_call

# --- 网页交互逻辑 ---
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
            
            df_result = process_data(df_call, df_ext)
            
            if df_result is not None:
                st.success("🎉 Part 1 数据清洗与 5 列扩充计算完美成功！")
                
                # 数据预览
                all_cols = list(df_result.columns)
                preview_cols = [c for c in ['酒店名称', '主叫号码', '通话状态', 'AI通话状态', '人工通话状态', '呼叫时间', 
                                '房间是否接入', '最终成功接通', '接通方式', '呼叫所在日期', '呼叫所在小时'] if c in all_cols]
                st.dataframe(df_result[preview_cols].head(5), use_container_width=True)
                
                # 下载按钮
                csv_buffer = df_result.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载扩充后的完整表格 (Part 1 结果)",
                    data=csv_buffer,
                    file_name="运营数据_已扩充_Part1.csv",
                    mime="text/csv"
                )
                
                # 留存给下一步
                st.session_state['df_part1_result'] = df_result
            
        except Exception as e:
            st.error(f"处理发生非预期错误: {e}")
else:
    st.info("💡 提示：请上传您刚才发给我的模版格式表格进行测试。")
