import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="내 주식 관리 파트너", layout="wide")
st.title("🕵️‍♂️ 자산 오차 범인 찾기 (검증 모드)")

# ---------------------------------------------------------
# [시장 지표]
def get_market_data():
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        treasury = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        nasdaq = yf.Ticker("^NDX").history(period="1d")['Close'].iloc[-1]
        return usd_krw, treasury, nasdaq
    except:
        return 0, 0, 0

st.markdown("### 🌍 주요 시장 지표")
col1, col2, col3 = st.columns(3)
with st.spinner("지표 로딩 중..."):
    rate, bond, ndx = get_market_data()
with col1: st.metric("🇺🇸 원/달러 환율", f"{rate:,.2f} 원")
with col2: st.metric("🏦 미국 10년물 금리", f"{bond:,.2f} %")
with col3: st.metric("💻 나스닥 100", f"{ndx:,.2f}")
st.divider()

# ---------------------------------------------------------
# [파일 저장 시스템]
CSV_FILE = 'my_portfolio.csv'

def load_data():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    else:
        default_data = [
            {"티커": "AAPL", "보유수량": 10.0, "목표비중(%)": 30},
            {"티커": "TSLA", "보유수량": 5.0, "목표비중(%)": 30},
        ]
        return pd.DataFrame(default_data)

df = load_data()

# ---------------------------------------------------------
st.sidebar.header("⚙️ 자산 설정")
monthly_investment = st.sidebar.number_input("➕ 이번 달 추가 투자금 ($)", value=1000.0, step=100.0)
current_cash = st.sidebar.number_input("💰 현재 계좌 보유 현금 ($)", value=0.0, step=10.0)

st.warning("👇 **[중요]** 증권사 어플과 비교할 때, 아래 표의 **'적용된 가격'**이 맞는지 꼭 확인하세요!")

edited_df = st.data_editor(
    df, 
    num_rows="dynamic",
    key="portfolio_editor",
    column_config={
        "보유수량": st.column_config.NumberColumn("보유수량", step=0.0001, format="%.4f"),
        "목표비중(%)": st.column_config.NumberColumn("목표비중(%)", min_value=0, max_value=100, format="%d%%"),
    }
)

if st.button("💾 저장 및 정밀 검증 시작"):
    
    edited_df.to_csv(CSV_FILE, index=False)
    st.success("✅ 저장 완료!")

    with st.spinner('가격 데이터 정밀 조회 중...'):
        final_data = []
        
        for index, row in edited_df.iterrows():
            ticker = row['티커']
            qty = float(row['보유수량']) if pd.notnull(row['보유수량']) else 0.0
            target_pct = float(row['목표비중(%)']) if pd.notnull(row['목표비중(%)']) else 0.0
            
            try:
                stock = yf.Ticker(ticker)
                # 최근 5일치 데이터를 가져와서 마지막 날짜 확인
                history = stock.history(period="5d")
                
                if not history.empty:
                    current_price = history['Close'].iloc[-1]
                    # 데이터 날짜 가져오기 (시간대 문제 해결을 위해 문자열로 변환)
                    last_date = history.index[-1].strftime('%Y-%m-%d')
                else:
                    current_price = 0
                    last_date = "데이터 없음"
            except:
                current_price = 0
                last_date = "오류"
            
            current_val = current_price * qty
            
            final_data.append({
                "티커": ticker,
                "보유수량": qty,
                "적용된 가격($)": current_price, # 사용자가 확인하기 쉽게 이름 변경
                "데이터 기준일": last_date,      # 언제 가격인지 보여줌
                "내 평가액($)": current_val,
                "목표비중(%)": target_pct
            })
            
        result_df = pd.DataFrame(final_data)
        
        if not result_df.empty:
            stock_assets = result_df['내 평가액($)'].sum()
            total_assets = stock_assets + current_cash
            final_total_assets = total_assets + monthly_investment
            
            st.markdown("### 🕵️‍♂️ 가격 검증 리포트")
            st.caption("아래 표에서 **'적용된 가격'**과 **'데이터 기준일'**을 확인해보세요. 증권사 어플과 가격이 다르다면, 장외거래 가격 차이일 수 있습니다.")
            
            # 검증용 테이블 출력
            check_cols = ['티커', '적용된 가격($)', '보유수량', '내 평가액($)', '데이터 기준일']
            st.dataframe(
                result_df[check_cols].style.format({
                    '적용된 가격($)': '${:,.2f}',
                    '보유수량': '{:.4f}',
                    '내 평가액($)': '${:,.2f}'
                })
            )
            
            st.divider()
            
            # 자산 현황
            col_sum1, col_sum2 = st.columns(2)
            with col_sum1:
                st.metric("📉 내 총 자산 (주식+현금)", f"${total_assets:,.2f}")
            with col_sum2:
                st.metric("🔮 투자 후 예상 자산", f"${final_total_assets:,.2f}")

            # 리밸런싱 계산
            result_df['목표금액($)'] = final_total_assets * (result_df['목표비중(%)'] / 100)
            result_df['부족한금액($)'] = result_df['목표금액($)'] - result_df['내 평가액($)']
            result_df['추천_매수수량'] = result_df.apply(lambda x: x['부족한금액($)'] / x['적용된 가격($)'] if (x['부족한금액($)'] > 0 and x['적용된 가격($)'] > 0) else 0, axis=1)
            result_df['예상매수비용($)'] = result_df['추천_매수수량'] * result_df['적용된 가격($)']

            st.subheader("🛒 매수 추천 가이드")
            st.dataframe(
                result_df[['티커', '적용된 가격($)', '추천_매수수량', '예상매수비용($)']].style.format({
                    '적용된 가격($)': '${:,.2f}',
                    '추천_매수수량': '{:.4f}',
                    '예상매수비용($)': '${:,.2f}'
                }).highlight_max(axis=0, subset=['예상매수비용($)'], color='#d1e7dd')
            )