import streamlit as st
import pandas as pd
import numpy as np
import io

# 设置网页标题与布局
st.set_page_config(page_title="语音数据智能分析工具", layout="wide")

st.title("📊 语音运营数据智能计算中心 - 6大指标逐项核对看板")
st.markdown("当前阶段：已严格按照添加和计算顺序，将所有基础量、率级指标以及中间流转过程数据完整无盲区平铺呈现。")

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
    with st.spinner("正在严格按照指标链条加总数据中..."):
        try:
            if uploaded_call_file.name.endswith('.csv'):
                df_call = pd.read_csv(uploaded_call_file)
            else:
                df_call = pd.read_excel(uploaded_call_file)
                
            if uploaded_ext_file.name.endswith('.csv'):
                df_ext = pd.read_csv(uploaded_ext_file)
            else:
                df_ext = pd.read_excel(uploaded_ext_file)
            
            # 执行底层清洗
            df_result = process_data(df_call, df_ext)
            
            if df_result is not None:
                st.success("🎉 全量指标矩阵重组成功，请依据下方流向依次检查数据：")
                
                # 客房过滤基准
                df_rooms = df_result[df_result['房间是否接入'] == '客房']
                
                # -----------------【数据计算流水线（按你的指定顺序）】-----------------
                
                # 指标 1：总来电量
                total_calls = int(len(df_rooms))
                
                # 指标 2：整体接通率（人工原口径）
                df_rooms['人工通话状态_clean'] = df_rooms['人工通话状态'].astype(str).str.strip()
                man_success_all = int((df_rooms['人工通话状态_clean'] == '接通').sum())
                man_failed_all = int((df_rooms['人工通话状态_clean'] == '未接通').sum())
                man_total_all = man_success_all + man_failed_all
                man_connect_rate_all_str = f"{man_success_all / man_total_all:.2%}" if man_total_all > 0 else "--"
                
                # 指标 3 & 4：上线后人工接通率相关的前置数据
                connect_types = df_rooms['接通方式'].astype(str).str.strip()
                # 3. 人工接通量（分子：情况A + 情况B）
                inc_ai_and_man_success = int((connect_types == '进入AI后，再转接人工，且人工接通').sum())
                direct_man_success = int((connect_types == '直接进入人工，且人工接通').sum())
                online_man_success_volume = inc_ai_and_man_success + direct_man_success
                
                # 4. 进入人工电话量（分母：4种情况之和）
                ai_success_man_failed = int((connect_types == 'AI接通，转接人工，人工未接通').sum())
                direct_man_failed = int((connect_types == '直接进入人工且最终未接通').sum())
                online_man_total_volume = ai_success_man_failed + direct_man_failed + inc_ai_and_man_success + direct_man_success
                
                # 5. 上线后人工接通率
                online_man_connect_rate_str = f"{online_man_success_volume / online_man_total_volume:.2%}" if online_man_total_volume > 0 else "--"
                
                # 指标 6 & 7：AI 接通率相关数据
                df_rooms['AI通话状态_clean'] = df_rooms['AI通话状态'].astype(str).str.strip()
                ai_success_volume = int((df_rooms['AI通话状态_clean'] == '接通').sum())
                ai_total_volume = int(df_rooms['AI通话状态_clean'].isin(['接通', '未接通']).sum())
                ai_connect_rate = ai_success_volume / ai_total_volume if ai_total_volume > 0 else 0.0
                ai_connect_rate_str = f"{ai_connect_rate:.2%}" if ai_total_volume > 0 else "--"
                
                # AI是否异常标记
                is_ai_abnormal = (ai_success_volume != ai_total_volume)
                
                # -----------------【前端顺序渲染区】-----------------
                
                st.markdown("### 🧭 第一阶段：基础话务量与传统人工承接")
                c_row1_1, c_row1_2, c_row1_3 = st.columns(3)
                with c_row1_1:
                    st.metric(label="1️⃣ 总来电量 (客房呼出)", value=f"{total_calls} 次")
                with c_row1_2:
                    st.metric(label="2️⃣ 整体接通率 (人工原口径)", value=man_connect_rate_all_str, help="人工接通 / 人工明确有状态总数")
                with c_row1_3:
                    st.caption(f"💡 传统口径参考：人工接通行数 `{man_success_all}` 次，人工未接通行数 `{man_failed_all}` 次。")

                st.markdown("---")
                
                st.markdown("### 🧭 第二阶段：上线后人工承接漏斗明细 (精细化口径)")
                c_row2_1, c_row2_2, c_row2_3 = st.columns(3)
                with c_row2_1:
                    st.metric(label="3️⃣ 人工接通量 (分子)", value=f"{online_man_success_volume} 次", help=f"进入AI转人工接通({inc_ai_and_man_success}) + 直接进入人工接通({direct_man_success})")
                with c_row2_2:
                    st.metric(label="4️⃣ 进入人工电话量 (分母)", value=f"{online_man_total_volume} 次", help="4种转接及直连人工状态的大合集")
                with c_row2_3:
                    st.metric(label="5️⃣ 上线后人工接通率", value=online_man_connect_rate_str, help="由【指标3 / 指标4】严格计算得出")
                
                st.markdown("---")
                
                st.markdown("### 🧭 第三阶段：AI 客服专项接通与完备性校验")
                c_row3_1, c_row3_2 = st.columns(2)
                with c_row3_1:
                    st.metric(label="6️⃣ AI话务对照组 (接通量 / 进入量)", value=f"{ai_success_volume} 次 / {ai_total_volume} 次")
                with c_row3_2:
                    if is_ai_abnormal:
                        st.markdown(
                            f"<div style='background-color:#FFD2D2; padding:12px; border-radius:5px; border-left:6px solid #FF0000;'>"
                            f"<p style='margin:0; color:#550000; font-size:14px; font-weight:bold;'>7️⃣ AI接通率 (⚠️触发不等预警)</p>"
                            f"<h2 style='margin:0; color:#CC0000;'>{ai_connect_rate_str}</h2>"
                            f"<p style='margin:0; color:#772222; font-size:12px;'>警告：当前底表统计到的 AI 接通数量与总进入量不一致，建议排查底层详单。</p>"
                            f"</div>", 
                            unsafe_allow_html=True
                        )
                    else:
                        st.metric(label="7️⃣ AI接通率 (标准健康)", value=ai_connect_rate_str, help="AI完全合流，目前数据呈现完美100%")

                st.markdown("---")
                
                # -----------------【导出模块完整重构】-----------------
                # 确保导出的电子表格也按照检查顺序排列
                df_summary = pd.DataFrame({
                    "顺序编号": ["1", "2", "3", "4", "5", "6", "7"],
                    "核心指标/数据项名称": [
                        "总来电量（所有启用AI的客房呼出的电话量）", 
                        "整体接通率（人工原口径）",
                        "人工接通量（上线后人工分子）",
                        "进入人工电话量（上线后人工分母）",
                        "上线后人工接通率（精细口径）",
                        "AI承接业务量对账（接通/全部）",
                        "AI接通率（常规应为100%）"
                    ],
                    "当前计算数值": [
                        total_calls, 
                        man_connect_rate_all_str,
                        f"{online_man_success_volume} 次",
                        f"{online_man_total_volume} 次",
                        online_man_connect_rate_str,
                        f"{ai_success_volume} / {ai_total_volume}",
                        ai_connect_rate_str
                    ],
                    "核对口径与公式说明": [
                        "COUNTIF 房间是否接入 == '客房'", 
                        "全部明确状态的人工接通 / 人工总通话",
                        "两种人工接通标准场景加总",
                        "包含转人工未接、直连未接、转人工已接、直连已接4类",
                        "人工接通量 / 进入人工电话量",
                        "AI单独成功接通数 与 AI交互数 对账",
                        f"AI接通量/进入AI量 {'(⚠️数据不对等风险)' if is_ai_abnormal else '（健康）'}"
                    ]
                })
                
                # 写入多工作表 Excel 
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_summary.to_excel(writer, sheet_name="核心运营报告首页", index=False)
                    df_result.to_excel(writer, sheet_name="云总机通话详单", index=False)
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="📥 下载已按顺序对齐的全新版本报告",
                    data=excel_data,
                    file_name="语音运营分析复盘报告_按序对齐版.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        except Exception as e:
            st.error(f"处理发生非预期错误: {e}")
else:
    st.info("💡 提示：请在上方上传表格，系统会自动以严格的流水顺序为你呈现对账看板。")
