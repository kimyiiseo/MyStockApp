import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os

# 페이지 설정
st.set_page_config(page_title="내 주식 관리 파트너", layout="wide")
st.title("📈 내 손안의 펀드매니저 (안전 버전)")

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
            {"티커": "NVDA", "보유수량": 2.0, "목표비중(%)": 20},
            {"티커": "MSFT", "보유수량": 3.0, "목표비중(%)": 10},
            {"티커": "GOOGL", "보유수량": 4.0, "목표비중(%)": 10},
        ]
        return pd.DataFrame(default_data)

df = load_data()
# ---------------------------------------------------------

st.sidebar.header("⚙️ 투자 설정")
monthly_investment = st.sidebar.number_input("이번 달 투자금 ($)", value=1000.0, step=100.0)

st.info("👇 아래 표를 수정하고 **'💾 변경사항 저장 및 계산'** 버튼을 누르세요.")

edited_df = st.data_editor(
    df, 
    num_rows="dynamic",
    key="portfolio_editor"
)

if st.button("💾 변경사항 저장 및 계산 시작"):
    
    # 1. 저장
    edited_df.to_csv(CSV_FILE, index=False)
    st.success("✅ 저장 완료!")

    # 2. 계산
    with st.spinner('주가를 조회하고 분석 중입니다...'):
        final_data = []
        
        for index, row in edited_df.iterrows():
            ticker = row['티커']
            qty = float(row['보유수량']) if pd.notnull(row['보유수량']) else 0.0
            target_pct = float(row['목표비중(%)']) if pd.notnull(row['목표비중(%)']) else 0.0
            
            # 주가 가져오기 (오류 발생 시 0원 처리)
            try:
                if ticker and isinstance(ticker, str):
                    stock = yf.Ticker(ticker)
                    history = stock.history(period="1d")
                    if not history.empty:
                        current_price = history['Close'].iloc[-1]
                    else:
                        current_price = 0
                else:
                    current_price = 0
            except:
                current_price = 0
            
            # 가격을 못 가져왔으면 경고 메시지 띄우기
            if current_price == 0:
                st.warning(f"⚠️ '{ticker}'의 가격을 가져오지 못했습니다. 티커를 확인하거나 잠시 후 다시 시도하세요.")

            current_val = current_price * qty
            
            final_data.append({
                "티커": ticker,
                "보유수량": qty,
                "현재가($)": current_price,
                "현재평가액($)": current_val,
                "목표비중(%)": target_pct
            })
            
        result_df = pd.DataFrame(final_data)
        
        # 합계 계산 (가격이 0인 종목은 제외하고 계산됨)
        if not result_df.empty:
            total_asset = result_df['현재평가액($)'].sum()
            total_new_asset = total_asset + monthly_investment
            
            st.divider()
            col_sum1, col_sum2 = st.columns(2)
            with col_sum1:
                st.metric(label="현재 총 자산", value=f"${total_asset:,.2f}")
            with col_sum2:
                st.metric(label="투자 후 예상 자산", value=f"${total_new_asset:,.2f}", delta=f"+${monthly_investment:,.2f}")

            # 리밸런싱 로직
            result_df['목표금액($)'] = total_new_asset * (result_df['목표비중(%)'] / 100)
            result_df['부족한금액($)'] = result_df['목표금액($)'] - result_df['현재평가액($)']
            
            # [핵심 수정] 현재가가 0보다 클 때만 나누기를 수행! (ZeroDivisionError 방지)
            result_df['추천_매수수량'] = result_df.apply(
                lambda x: x['부족한금액($)'] / x['현재가($)'] if (x['부족한금액($)'] > 0 and x['현재가($)'] > 0) else 0, 
                axis=1
            )
            
            result_df['예상매수비용($)'] = result_df['추천_매수수량'] * result_df['현재가($)']

            # 결과 표 출력
            st.subheader("🛒 매수 추천 가이드")
            display_cols = ['티커', '현재가($)', '목표비중(%)', '추천_매수수량', '예상매수비용($)']
            
            st.dataframe(
                result_df[display_cols].style.format({
                    '현재가($)': '${:,.2f}',
                    '추천_매수수량': '{:,.4f}',
                    '예상매수비용($)': '${:,.2f}'
                }).highlight_max(axis=0, subset=['예상매수비용($)'], color='#d1e7dd')
            )
            
            # 차트 출력
            st.subheader("📊 포트폴리오 비중")
            if total_asset > 0:
                fig, ax = plt.subplots()
                ax.pie(result_df['현재평가액($)'], labels=result_df['티커'], autopct='%1.1f%%', startangle=90)
                st.pyplot(fig)
            else:
                st.info("표시할 자산 데이터가 없습니다.")
            
        else:
            st.error("데이터를 처리할 수 없습니다.")