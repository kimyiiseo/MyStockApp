import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# [설정 구역] 소수점 수량 입력 가능!
# ---------------------------------------------------------
my_portfolio = {
    "AAPL": {"quantity": 10.523, "target_percent": 30},  # 예: 10.523주 보유
    "TSLA": {"quantity": 5.12, "target_percent": 30},    # 예: 5.12주 보유
    "NVDA": {"quantity": 2.0, "target_percent": 20},
    "MSFT": {"quantity": 3.5, "target_percent": 10},
    "GOOGL": {"quantity": 4.1, "target_percent": 10},
}
# ---------------------------------------------------------

st.set_page_config(page_title="내 주식 자동 관리", layout="wide")

st.title("📈 소수점 투자 리밸런싱 계산기")
st.caption("소수점 단위까지 정밀하게 계산합니다.")

st.sidebar.header("💰 투자금 설정")
monthly_investment = st.sidebar.number_input("이번 달 투자할 금액 ($)", value=1000.0, step=100.0)

if st.button("🚀 주식 데이터 가져오기 (클릭)"):
    with st.spinner('가격 조회 중...'):
        
        portfolio_data = []
        
        for ticker, info in my_portfolio.items():
            stock = yf.Ticker(ticker)
            try:
                history = stock.history(period="1d")
                current_price = history['Close'].iloc[-1]
            except:
                st.error(f"{ticker} 오류")
                current_price = 0
            
            # 소수점 수량 그대로 계산
            current_value = current_price * info['quantity']
            
            portfolio_data.append({
                "티커": ticker,
                "보유수량": info['quantity'],
                "현재가($)": current_price, 
                "현재평가액($)": current_value,
                "목표비중(%)": info['target_percent']
            })

        df = pd.DataFrame(portfolio_data)
        
        total_asset = df['현재평가액($)'].sum()
        total_new_asset = total_asset + monthly_investment
        
        st.write(f"### 💎 내 총 자산: ${total_asset:,.2f}")
        st.write(f"### 💵 투자 후 예상 자산: ${total_new_asset:,.2f}")

        # 리밸런싱 계산
        df['목표금액($)'] = total_new_asset * (df['목표비중(%)'] / 100)
        df['부족한금액($)'] = df['목표금액($)'] - df['현재평가액($)']
        
        # [핵심 변경] int()를 빼서 소수점 계산이 되도록 변경!
        # 매수 수량 = 부족한 금액 / 현재가 (소수점 4자리까지 표시)
        df['추천_매수수량'] = df.apply(lambda x: x['부족한금액($)'] / x['현재가($)'] if x['부족한금액($)'] > 0 else 0, axis=1)
        
        df['예상매수비용($)'] = df['추천_매수수량'] * df['현재가($)']

        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🛒 소수점 매수 가이드")
            display_df = df[['티커', '현재가($)', '보유수량', '목표비중(%)', '추천_매수수량', '예상매수비용($)']]
            
            # 소수점 4자리까지 깔끔하게 보여주기 포맷팅
            st.dataframe(display_df.style.format({
                '현재가($)': '${:,.2f}',
                '보유수량': '{:,.4f}',      # 소수점 4자리
                '추천_매수수량': '{:,.4f}', # 소수점 4자리
                '예상매수비용($)': '${:,.2f}'
            }).highlight_max(axis=0, subset=['추천_매수수량'], color='#ffffcc'))
            
        with col2:
            st.subheader("📊 비중 분석")
            current_ratios = df['현재평가액($)'] / total_asset * 100
            fig, ax = plt.subplots()
            ax.pie(current_ratios, labels=df['티커'], autopct='%1.1f%%', startangle=90)
            st.pyplot(fig)

else:
    st.info("버튼을 눌러주세요.")