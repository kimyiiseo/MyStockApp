import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os
from datetime import datetime

# ---------------------------------------------------------
# [기본 설정]
# ---------------------------------------------------------
st.set_page_config(page_title="내 주식 파트너", layout="wide")
st.title("📈 내 자산 관리 시스템 (All-in-One)")

CSV_FILE = 'my_portfolio.csv'
HISTORY_FILE = 'trade_history.csv' # 매수 기록 저장용 파일

# 데이터 로드 함수
def load_data():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    else:
        default_data = [
            {"티커": "AAPL", "보유수량": 10.0, "목표비중(%)": 30},
            {"티커": "TSLA", "보유수량": 5.0, "목표비중(%)": 30},
            {"티커": "NVDA", "보유수량": 2.0, "목표비중(%)": 20},
            {"티커": "SCHD", "보유수량": 10.0, "목표비중(%)": 20},
        ]
        return pd.DataFrame(default_data)

# 매수 기록 로드 함수
def load_history():
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    else:
        return pd.DataFrame(columns=["날짜", "티커", "매수단가($)", "매수수량", "총액($)"])

# ---------------------------------------------------------
# [사이드바] 자산 설정
# ---------------------------------------------------------
st.sidebar.header("💰 자산 설정")
monthly_investment = st.sidebar.number_input("➕ 이번 달 투자금 ($)", value=340.0, step=10.0)
current_cash = st.sidebar.number_input("💵 현재 보유 예수금 ($)", value=0.0, step=10.0)
available_budget = monthly_investment + current_cash

st.sidebar.markdown(f"### 💼 총 투자 가능 금액: **${available_budget:,.2f}**")

# ---------------------------------------------------------
# [메인 화면] 탭 구성
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 리밸런싱 계산기", "📝 매수 기록 입력", "📜 매매 일지"])

# =========================================================
# [탭 1] 리밸런싱 계산기 (예산 초과 해결 버전)
# =========================================================
with tab1:
    st.markdown("### 🛒 이번 달 무엇을 사야 할까요?")
    st.caption("가진 돈(예산) 안에서 비율이 가장 부족한 종목을 자동으로 계산해 줍니다.")

    df = load_data()
    
    # 데이터 에디터 (수정 가능)
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic",
        key="portfolio_editor",
        column_config={
            "보유수량": st.column_config.NumberColumn("보유수량", step=0.0001, format="%.4f"),
            "목표비중(%)": st.column_config.NumberColumn("목표비중(%)", min_value=0, max_value=100, format="%d%%"),
        }
    )

    if st.button("💾 설정 저장 및 계산 시작", key="calc_btn"):
        edited_df.to_csv(CSV_FILE, index=False)
        
        with st.spinner('시장 가격 조회 및 최적 비율 계산 중...'):
            final_data = []
            
            # 1. 현재가 조회 및 현재 자산 계산
            for index, row in edited_df.iterrows():
                ticker = row['티커']
                qty = float(row['보유수량']) if pd.notnull(row['보유수량']) else 0.0
                target_pct = float(row['목표비중(%)']) if pd.notnull(row['목표비중(%)']) else 0.0
                
                try:
                    stock = yf.Ticker(ticker)
                    history = stock.history(period="1d")
                    current_price = history['Close'].iloc[-1] if not history.empty else 0
                except:
                    current_price = 0
                
                final_data.append({
                    "티커": ticker,
                    "보유수량": qty,
                    "현재가($)": current_price,
                    "현재평가액($)": current_price * qty,
                    "목표비중(%)": target_pct
                })
            
            result_df = pd.DataFrame(final_data)
            
            if not result_df.empty:
                # 2. 전체 자산 규모 파악
                total_stock_value = result_df['현재평가액($)'].sum()
                # 시뮬레이션 총 자산 = 주식 + 현금 + 투자금
                simulated_total_asset = total_stock_value + available_budget
                
                st.divider()
                c1, c2 = st.columns(2)
                c1.metric("현재 주식 자산", f"${total_stock_value:,.2f}")
                c2.metric("리밸런싱 기준 총 자산", f"${simulated_total_asset:,.2f}")
                
                # 3. 목표 금액 계산
                result_df['이상적_목표금액($)'] = simulated_total_asset * (result_df['목표비중(%)'] / 100)
                result_df['부족한금액($)'] = result_df['이상적_목표금액($)'] - result_df['현재평가액($)']
                
                # 4. [핵심] 예산 비례 배분 로직
                # 부족한 금액이 양수(+)인 종목들만 모음 (사야 할 애들)
                buy_candidates = result_df[result_df['부족한금액($)'] > 0].copy()
                total_needed = buy_candidates['부족한금액($)'].sum()
                
                # 만약 사야 할 돈이 예산보다 많으면? -> 예산만큼만 비율대로 줄여서 산다!
                if total_needed > available_budget:
                    # 비율 = 내 예산 / 필요한 총액
                    ratio = available_budget / total_needed
                    result_df['배정된_매수금액($)'] = result_df['부족한금액($)'].apply(lambda x: x * ratio if x > 0 else 0)
                else:
                    # 예산이 충분하면 부족한 만큼 다 산다
                    result_df['배정된_매수금액($)'] = result_df['부족한금액($)'].apply(lambda x: x if x > 0 else 0)
                
                # 5. 수량 계산
                result_df['추천_매수수량'] = result_df.apply(
                    lambda x: x['배정된_매수금액($)'] / x['현재가($)'] if x['현재가($)'] > 0 else 0, axis=1
                )
                
                # 6. 결과 출력
                st.subheader("🛒 스마트 매수 추천 (예산 맞춤)")
                st.caption(f"💡 설정하신 예산 **${available_budget:,.2f}** 내에서 최적의 비율로 배분했습니다.")
                
                display_df = result_df[['티커', '현재가($)', '목표비중(%)', '추천_매수수량', '배정된_매수금액($)']]
                st.dataframe(
                    display_df.style.format({
                        '현재가($)': '${:,.2f}',
                        '추천_매수수량': '{:.4f}',
                        '배정된_매수금액($)': '${:,.2f}'
                    }).highlight_max(axis=0, subset=['배정된_매수금액($)'], color='#d1e7dd')
                )
                
                # 합계 검증
                total_spend = result_df['배정된_매수금액($)'].sum()
                st.info(f"🧾 총 매수 예정 금액: **${total_spend:,.2f}** (잔액: ${available_budget - total_spend:,.2f})")

# =========================================================
# [탭 2] 매수 기록 입력 (자동 업데이트)
# =========================================================
with tab2:
    st.markdown("### 📝 매수하셨나요? 여기에 기록하세요!")
    st.caption("기록하면 포트폴리오 수량이 자동으로 늘어납니다.")
    
    current_portfolio = load_data()
    ticker_list = current_portfolio['티커'].tolist()
    
    with st.form("buy_form"):
        col_input1, col_input2 = st.columns(2)
        
        with col_input1:
            date_input = st.date_input("매수 날짜", datetime.today())
            ticker_input = st.selectbox("종목 선택", ticker_list)
        
        with col_input2:
            price_input = st.number_input("매수 단가 ($)", min_value=0.0, step=0.01, format="%.2f")
            qty_input = st.number_input("매수 수량", min_value=0.0, step=0.0001, format="%.4f")
        
        submit_btn = st.form_submit_button("✅ 매수 기록 저장하기")
        
        if submit_btn:
            if price_input > 0 and qty_input > 0:
                # 1. my_portfolio.csv 업데이트 (수량 추가)
                current_portfolio.loc[current_portfolio['티커'] == ticker_input, '보유수량'] += qty_input
                current_portfolio.to_csv(CSV_FILE, index=False)
                
                # 2. trade_history.csv 업데이트 (기록 추가)
                history_df = load_history()
                new_record = pd.DataFrame([{
                    "날짜": date_input,
                    "티커": ticker_input,
                    "매수단가($)": price_input,
                    "매수수량": qty_input,
                    "총액($)": price_input * qty_input
                }])
                
                # pandas 버전에 따라 append 대신 concat 사용
                history_df = pd.concat([new_record, history_df], ignore_index=True)
                history_df.to_csv(HISTORY_FILE, index=False)
                
                st.success(f"🎉 저장 완료! {ticker_input} {qty_input}주가 포트폴리오에 추가되었습니다.")
                st.rerun() # 화면 새로고침
            else:
                st.error("가격과 수량을 정확히 입력해주세요.")

# =========================================================
# [탭 3] 매매 일지 (기록 보기)
# =========================================================
with tab3:
    st.markdown("### 📜 나의 매매 기록")
    history_view = load_history()
    
    if not history_view.empty:
        st.dataframe(
            history_view.style.format({
                "매수단가($)": "${:,.2f}",
                "매수수량": "{:.4f}",
                "총액($)": "${:,.2f}"
            })
        )
    else:
        st.info("아직 매매 기록이 없습니다. '매수 기록 입력' 탭에서 기록을 추가해보세요!")