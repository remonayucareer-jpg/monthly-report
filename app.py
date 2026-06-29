import streamlit as st
import pandas as pd
import numpy as np

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 语音运营数据智能计算中心 - Part 1")
st.markdown("请在下方上传您的**运营数据**和**分机号表**，系统将自动完成第一阶段的 5 行数据扩充计算。")

# 创建上传组件
col1, col2 = st.columns(2)
with col1:
    uploaded_call_file = st.file_uploader("1. 请上传【运营数据表格】(支持 CSV / XLSX)", type=["csv", "xlsx"])
with col2:
    uploaded_ext_file = st.file_uploader("2. 请上传【分机号参考表格】(支持 CSV / XLSX)", type=["csv", "xlsx"])

# 核心计算函数
def process_data(df_call, df_ext):
    # --- 数据清洗与预处理 ---
    # 将匹配主键转换为去除了空格的字符串，确保 100% 精确匹配
    df_call['主叫号码_str'] = df_call['主叫号码'].astype(str).str.strip()
    df_ext['分机号_str'] = df_ext['分机号'].astype(str).str.strip()
    
    # 获取所有存在的分机号集合
    valid_extensions = set(df_ext['分机号_str'].unique())
    
    # 1. 计算【房间是否接入】
    # 如果主叫号码在分机号表里存在，则定义为“客房”，否则为“--”
    df_call['房间是否接入'] = df_call['主叫号码_str'].apply(
        lambda x: '客房' if x in valid_extensions else '--'
    )
    
    # 2. 计算【最终成功接通】
    def check_final_success(row):
        if row['房间是否接入'] != '客房':
            return '--'
        m = str(row['通话状态']).strip()
        n = str(row['AI通话状态']).strip()
        o = str(row['人工通话状态']).strip()
        
        # 对应您的 Excel 公式组合条件
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
        m = str(row['通话状态']).strip()
        n = str(row['AI通话状态']).strip()
        o = str(row['人工通话状态']).strip()
        
        # 条件 1：进入AI后，再转接人工，且人工接通
        if m == '接通' and n == '接通' and o == '接通':
            return '进入AI后，再转接人工，且人工接通'
        # 条件 2：AI接通，转接人工，人工未接通
        elif m == '接通' and n == '接通' and o == '未接通':
            return 'AI接通，转接人工，人工未接通'
        # 条件 3：进入AI后，AI直接完成，未转接人工
        elif m == '接通' and n == '接通' and o == '--':
            return '进入AI后，AI直接完成，未转接人工'
        # 条件 4：直接进入人工，且人工接通
        elif m == '接通' and n == '--' and o == '接通':
            return '直接进入人工，且人工接通'
        # 条件 5：客人主动挂断
        elif m == '未接通' and n == '--' and o == '--':
            return '客人主动挂断'
        # 条件 6：直接进入人工且最终未接通
        elif m == '未接通' and n == '--' and o == '未接通':
            return '直接进入人工且最终未接通'
        # 如果不满足以上任何条件，输出异常
        else:
            return '异常'

    df_call['接通方式'] = df_call.apply(check_connect_type, axis=1)
    
    # 4 & 5. 计算【呼叫所在日期】和【呼叫所在小时】
    # 将时间列转换为标准的 Pandas Datetime 格式
    call_time_parsed = pd.to_datetime(df_call['呼叫时间'], errors='coerce')
    df_call['呼叫所在日期'] = call_time_parsed.dt.strftime('%Y-%m-%d')
    # 如果转化失败保留整数，正常转则提取 hour
    df_call['呼叫所在小时'] = call_time_parsed.dt.hour.fillna(-1).astype(int).astype(str).replace('-1', '--')
    
    # 清理掉用于匹配的临时辅助列
    df_call = df_call.drop(columns=['主叫号码_str'])
    
    return df_call

# --- 网页交互逻辑 ---
if uploaded_call_file and uploaded_ext_file:
    with st.spinner("正在努力读取并计算数据，请稍候..."):
        try:
            # 根据文件类型进行读取
            if uploaded_call_file.name.endswith('.csv'):
                df_call = pd.read_csv(uploaded_call_file)
            else:
                df_call = pd.read_excel(uploaded_call_file)
                
            if uploaded_ext_file.name.endswith('.csv'):
                df_ext = pd.read_csv(uploaded_ext_file)
            else:
                df_ext = pd.read_excel(uploaded_ext_file)
            
            # 执行核心扩充计算
            df_result = process_data(df_call, df_ext)
            
            st.success("🎉 数据扩充计算完成！")
            
            # 展示计算完成后的预览数据（前5行）
            st.markdown("### 🔍 扩充后的数据预览 (前 5 行)")
            preview_cols = ['酒店名称', '主叫号码', '通话状态', 'AI通话状态', '人工通话状态', '呼叫时间', 
                            '房间是否接入', '最终成功接通', '接通方式', '呼叫所在日期', '呼叫所在小时']
            st.dataframe(df_result[preview_cols].head(5), use_container_width=True)
            
            # 提供下载按钮，方便测试
            csv_buffer = df_result.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载扩充后的完整表格 (Part 1 结果)",
                data=csv_buffer,
                file_name="运营数据_已扩充_Part1.csv",
                mime="text/csv"
            )
            
            # 将处理后的 DataFrame 存储到 session_state 中，供后续 Part 计算使用
            st.session_state['df_part1_result'] = df_result
            
        except Exception as e:
            st.error(f"数据处理时发生错误，请检查表格结构。错误信息: {e}")
else:
    st.info("💡 提示：请同时上传上方两个表格以解锁计算功能。")