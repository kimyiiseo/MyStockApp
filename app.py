import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os

# 페이지 설정
st.set_page_config(page_title="내 주식 관리 파트너", layout="wide")
st.title("📈 내 손안의 펀드매니저 (Pro)")

# ---------------------------------------------------------
# 1. [시장 지표] 실시간 데이터를 가져오는 함수
# ---------------------------------------------------------
def get_market_data():
    try:
        # 환율 (USD/KRW)
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        # 미국 10년물 국채 금리 (^TNX)
        treasury = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        # 나스닥 100 지수 (^NDX)
        nasdaq = yf.Ticker("^NDX").history(period="1d")['Close'].iloc[-1]
        
        return usd_krw, treasury, nasdaq
    except:
        return 0, 0, 0

# 화면 맨 위에 지표 띄우기
st.markdown("### 🌍 주요 시장 지표")
col1, col2, col3 = st.columns(3)

# 데이터 가져오기 (로딩 중엔 잠시 기다려주세요)
with st.spinner("시장 지표를 불러오는 중..."):
    rate, bond, ndx = get_market_data()

with col1:
    st.metric(label="🇺🇸 원/달러 환율", value=f"{rate:,.2f} 원")
with col2:
    st.metric(label="🏦 미국 10년물 국채금리", value=f"{bond:,.2f} %")
with col3:
    st.metric(label="💻 나스닥 100 지수", value=f"{ndx:,.2f}")

st.divider() # 구분선

# ---------------------------------------------------------
# [뉴스 센터] 버튼 클릭으로 뉴스 보기
# ---------------------------------------------------------
st.markdown("### 📰 실시간 경제 뉴스")
col_n1, col_n2, col_n3, col_n4 = st.columns(4)

with col_n1:
    st.link_button("🇺🇸 연준(Fed) 금리 뉴스", "https://www.google.com/search?q=Federal+Reserve+Interest+Rate+News&tbm=nws")
with col_n2:
    st.link_button("💴 달러/엔 환율 뉴스", "https://www.google.com/search?q=JPY+KRW+Exchange+Rate+News&tbm=nws")
with col_n3:
    st.link_button("📉 엔캐리 트레이드", "https://www.google.com/search?q=Yen+Carry+Trade+Unwinding&tbm=nws")
with col_n4:
    st.link_button("🤖 미국 기술주 속보", "https://www.google.com/search?q=US+Tech+Stocks+News&tbm=nws")

st.divider() # 구분선

# ---------------------------------------------------------
# [파일 저장 시스템]
CSV_FILE = 'my_portfolio.csv'

def load_data():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    else:
        default_data = [
            {"티커": "AAPL", "보유수량": 10.55, "목표비중(%)": 30},
            {"티커": "TSLA", "보유수량": 5.123, "목표비중(%)": 30},
            {"티커": "NVDA", "보유수량": 2.0, "목표비중(%)": 20},
            {"티커": "MSFT", "보유수량": 3.0, "목표비중(%)": 10},
            {"티커": "GOOGL", "보유수량": 4.0, "목표비중(%)": 10},
        ]
        return pd.DataFrame(default_data)

df = load_data()
# ---------------------------------------------------------

st.markdown("### 💼 내 포트폴리오 관리")
st.sidebar.header("⚙️ 투자 설정")
monthly_investment = st.sidebar.number_input("이번 달 투자금 ($)", value=1000.0, step=100.0)

st.info("👇 보유수량과 목표비중을 수정하고 **'💾 저장 및 계산'** 버튼을 누르세요.")

edited_df = st.data_editor(
    df, 
    num_rows="dynamic",
    key="portfolio_editor",
    column_config={
        "보유수량": st.column_config.NumberColumn(
            "보유수량",
            min_value=0,
            max_value=100000,
            step=0.0001,
            format="%.4f"
        ),
        "목표비중(%)": st.column_config.NumberColumn(
            "목표비중(%)",
            min_value=0,
            max_value=100,
            step=1,
            format="%d%%"
        ),
    }
)

if st.button("💾 변경사항 저장 및 계산 시작"):
    
    edited_df.to_csv(CSV_FILE, index=False)
    st.success("✅ 저장 완료!")

    with st.spinner('개별 종목 분석 중...'):
        final_data = []
        
        for index, row in edited_df.iterrows():
            ticker = row['티커']
            qty = float(row['보유수량']) if pd.notnull(row['보유수량']) else 0.0
            target_pct = float(row['목표비중(%)']) if pd.notnull(row['목표비중(%)']) else 0.0
            
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
            
            if current_price == 0:
                st.warning(f"⚠️ '{ticker}' 가격 로딩 실패.")

            current_val = current_price * qty
            
            final_data.append({
                "티커": ticker,
                "보유수량": qty,
                "현재가($)": current_price,
                "현재평가액($)": current_val,
                "목표비중(%)": target_pct
            })
            
        result_df = pd.DataFrame(final_data)
        
        if not result_df.empty:
            total_asset = result_df['현재평가액($)'].sum()
            total_new_asset = total_asset + monthly_investment
            
            # [수정] 원화 환산 자산 보여주기 (보너스 기능!)
            # 위에서 구한 환율(rate)을 활용
            rate, _, _ = get_market_data()
            krw_asset = total_asset * rate if rate > 0 else 0
            
            col_sum1, col_sum2 = st.columns(2)
            with col_sum1:
                st.metric(label="현재 총 자산 (USD)", value=f"${total_asset:,.2f}")
                st.caption(f"🇰🇷 약 {krw_asset:,.0f} 원") # 원화 가치 표시
            with col_sum2:
                st.metric(label="투자 후 예상 자산 (USD)", value=f"${total_new_asset:,.2f}")

            result_df['목표금액($)'] = total_new_asset * (result_df['목표비중(%)'] / 100)
            result_df['부족한금액($)'] = result_df['목표금액($)'] - result_df['현재평가액($)']
            
            result_df['추천_매수수량'] = result_df.apply(
                lambda x: x['부족한금액($)'] / x['현재가($)'] if (x['부족한금액($)'] > 0 and x['현재가($)'] > 0) else 0, 
                axis=1
            )
            result_df['예상매수비용($)'] = result_df['추천_매수수량'] * result_df['현재가($)']

            st.subheader("🛒 매수 추천 가이드")
            display_cols = ['티커', '현재가($)', '목표비중(%)', '추천_매수수량', '예상매수비용($)']
            
            st.dataframe(
                result_df[display_cols].style.format({
                    '현재가($)': '${:,.2f}',
                    '추천_매수수량': '{:.4f}',
                    '예상매수비용($)': '${:,.2f}'
                }).highlight_max(axis=0, subset=['예상매수비용($)'], color='#d1e7dd')
            )
            
            if total_asset > 0:
                st.subheader("📊 포트폴리오 비중")
                fig, ax = plt.subplots()
                ax.pie(result_df['현재평가액($)'], labels=result_df['티커'], autopct='%1.1f%%', startangle=90)
                st.pyplot(fig)