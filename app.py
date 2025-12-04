import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os
from datetime import datetime

# ---------------------------------------------------------
# [기본 설정] 페이지 설정은 항상 맨 위에!
# ---------------------------------------------------------
st.set_page_config(page_title="내 주식 파트너", layout="wide")
st.title("📈 내 자산 관리 시스템 (Master Ver.)")

CSV_FILE = 'my_portfolio.csv'
HISTORY_FILE = 'trade_history.csv'

# ---------------------------------------------------------
# [함수 모음] 데이터 로드 및 시장 지표
# ---------------------------------------------------------
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

def load_history():
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    else:
        return pd.DataFrame(columns=["날짜", "티커", "구분", "단가($)", "수량", "총액($)"])

def get_market_data():
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        treasury = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        nasdaq = yf.Ticker("^NDX").history(period="1d")['Close'].iloc[-1]
        return usd_krw, treasury, nasdaq
    except:
        return 0, 0, 0

# ---------------------------------------------------------
# [상단] 시장 지표 표시
# ---------------------------------------------------------
st.markdown("### 🌍 실시간 시장 지표")
col_m1, col_m2, col_m3 = st.columns(3)
with st.spinner("시장 지표 로딩 중..."):
    rate, bond, ndx = get_market_data()

with col_m1: st.metric("🇺🇸 원/달러 환율", f"{rate:,.2f} 원")
with col_m2: st.metric("🏦 미국 10년물 금리", f"{bond:,.2f} %")
with col_m3: st.metric("💻 나스닥 100", f"{ndx:,.2f}")
st.divider()

# ---------------------------------------------------------
# [사이드바] 자산 설정
# ---------------------------------------------------------
st.sidebar.header("💰 자산 설정")
monthly_investment = st.sidebar.number_input("➕ 이번 달 추가 투자금 ($)", value=340.0, step=10.0)
current_cash = st.sidebar.number_input("💵 현재 보유 예수금 ($)", value=0.0, step=10.0)
available_budget = monthly_investment + current_cash

st.sidebar.markdown(f"### 💼 총 매수 가용 자금: **${available_budget:,.2f}**")
st.sidebar.info("💡 매도를 통해 생긴 현금은 '보유 예수금'에 더해서 다시 계산하면 됩니다.")

# ---------------------------------------------------------
# [메인 화면] 탭 구성
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 리밸런싱 (매수/매도)", "📝 거래 기록 입력", "📜 거래 내역 조회"])

# =========================================================
# [탭 1] 리밸런싱 계산기 (매수 + 매도 분리)
# =========================================================
with tab1:
    st.markdown("### ⚖️ 포트폴리오 균형 맞추기")
    st.caption("왼쪽은 **더 사야 할 종목(Buy)**, 오른쪽은 **팔아야 할 종목(Sell)**입니다.")

    df = load_data()
    
    # 데이터 에디터
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic",
        key="portfolio_editor",
        column_config={
            "보유수량": st.column_config.NumberColumn("보유수량", step=0.0001, format="%.4f"),
            "목표비중(%)": st.column_config.NumberColumn("목표비중(%)", min_value=0, max_value=100, format="%d%%"),
        }
    )

    if st.button("💾 저장 및 분석 시작", key="calc_btn"):
        edited_df.to_csv(CSV_FILE, index=False)
        
        with st.spinner('가격 조회 및 리밸런싱 계산 중...'):
            final_data = []
            
            # 1. 데이터 가져오기
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
                # 2. 자산 계산
                total_stock_value = result_df['현재평가액($)'].sum()
                simulated_total_asset = total_stock_value + available_budget
                
                # 3. 목표 금액 및 차이 계산
                result_df['이상적_목표금액($)'] = simulated_total_asset * (result_df['목표비중(%)'] / 100)
                result_df['부족한금액($)'] = result_df['이상적_목표금액($)'] - result_df['현재평가액($)']
                
                # -----------------------------------------------------
                # [매수 로직] 부족한 금액이 (+)인 경우
                # -----------------------------------------------------
                buy_df = result_df[result_df['부족한금액($)'] > 0].copy()
                
                if not buy_df.empty:
                    total_needed = buy_df['부족한금액($)'].sum()
                    # 예산 비례 배분
                    if total_needed > available_budget:
                        ratio = available_budget / total_needed
                        buy_df['배정된_매수금액($)'] = buy_df['부족한금액($)'] * ratio
                    else:
                        buy_df['배정된_매수금액($)'] = buy_df['부족한금액($)']
                    
                    buy_df['추천_수량'] = buy_df.apply(lambda x: x['배정된_매수금액($)'] / x['현재가($)'] if x['현재가($)'] > 0 else 0, axis=1)
                
                # -----------------------------------------------------
                # [매도 로직] 부족한 금액이 (-)인 경우 -> 즉, 남는 경우
                # -----------------------------------------------------
                sell_df = result_df[result_df['부족한금액($)'] < 0].copy()
                
                if not sell_df.empty:
                    # 마이너스 값을 양수로 바꿔서 보여줌
                    sell_df['매도해야할금액($)'] = sell_df['부족한금액($)'].abs()
                    sell_df['추천_수량'] = sell_df.apply(lambda x: x['매도해야할금액($)'] / x['현재가($)'] if x['현재가($)'] > 0 else 0, axis=1)

                # -----------------------------------------------------
                # 화면 출력 (2단 분리)
                # -----------------------------------------------------
                st.divider()
                col_buy, col_sell = st.columns(2)
                
                # [왼쪽] 매수 추천
                with col_buy:
                    st.success("🛒 **매수(Buy) 추천**")
                    if not buy_df.empty:
                        st.dataframe(
                            buy_df[['티커', '현재가($)', '추천_수량', '배정된_매수금액($)']].style.format({
                                '현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '배정된_매수금액($)': '${:,.2f}'
                            })
                        )
                        st.caption(f"총 매수 예정: ${buy_df['배정된_매수금액($)'].sum():,.2f}")
                    else:
                        st.info("매수할 종목이 없습니다.")

                # [오른쪽] 매도 추천
                with col_sell:
                    st.error("📉 **매도(Sell) 추천** (과비중 조절)")
                    if not sell_df.empty:
                        st.dataframe(
                            sell_df[['티커', '현재가($)', '추천_수량', '매도해야할금액($)']].style.format({
                                '현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '매도해야할금액($)': '${:,.2f}'
                            })
                        )
                        st.caption(f"⚠️ 목표 비중보다 많이 보유 중인 종목들입니다.")
                    else:
                        st.info("매도할 종목이 없습니다. 비율이 좋습니다!")

# =========================================================
# [탭 2] 거래 기록 입력 (매수/매도 선택 가능)
# =========================================================
with tab2:
    st.markdown("### 📝 거래 기록 남기기")
    
    current_portfolio = load_data()
    ticker_list = current_portfolio['티커'].tolist()
    
    with st.form("trade_form"):
        col_input1, col_input2, col_input3 = st.columns(3)
        
        with col_input1:
            trade_type = st.selectbox("거래 구분", ["매수(Buy)", "매도(Sell)"])
            date_input = st.date_input("거래 날짜", datetime.today())
        
        with col_input2:
            ticker_input = st.selectbox("종목 선택", ticker_list)
            price_input = st.number_input("체결 단가 ($)", min_value=0.0, step=0.01)
        
        with col_input3:
            qty_input = st.number_input("체결 수량", min_value=0.0, step=0.0001, format="%.4f")
        
        submit_btn = st.form_submit_button("✅ 거래 기록 저장하기")
        
        if submit_btn:
            if price_input > 0 and qty_input > 0:
                # 1. 포트폴리오 수량 업데이트
                if trade_type == "매수(Buy)":
                    current_portfolio.loc[current_portfolio['티커'] == ticker_input, '보유수량'] += qty_input
                    action_code = "매수"
                else:
                    current_portfolio.loc[current_portfolio['티커'] == ticker_input, '보유수량'] -= qty_input
                    action_code = "매도"
                
                current_portfolio.to_csv(CSV_FILE, index=False)
                
                # 2. 거래 내역 저장
                history_df = load_history()
                new_record = pd.DataFrame([{
                    "날짜": date_input,
                    "티커": ticker_input,
                    "구분": action_code,
                    "단가($)": price_input,
                    "수량": qty_input,
                    "총액($)": price_input * qty_input
                }])
                
                history_df = pd.concat([new_record, history_df], ignore_index=True)
                history_df.to_csv(HISTORY_FILE, index=False)
                
                st.success(f"🎉 {ticker_input} {action_code} 기록 저장 완료!")
                st.rerun()

# =========================================================
# [탭 3] 거래 내역 조회
# =========================================================
with tab3:
    st.markdown("### 📜 나의 투자 발자취")
    history_view = load_history()
    if not history_view.empty:
        st.dataframe(history_view)
    else:
        st.info("아직 거래 기록이 없습니다.")

# ---------------------------------------------------------
# [하단] 뉴스 센터 (복구 완료!)
# ---------------------------------------------------------
st.divider()
st.markdown("### 📰 실시간 경제 뉴스 & 인사이트")
col_n1, col_n2, col_n3, col_n4 = st.columns(4)

with col_n1:
    st.link_button("🇺🇸 연준(Fed) 금리", "https://www.google.com/search?q=Federal+Reserve+Interest+Rate+News&tbm=nws")
with col_n2:
    st.link_button("💴 엔/달러 환율", "https://www.google.com/search?q=JPY+USD+Exchange+Rate+News&tbm=nws")
with col_n3:
    st.link_button("🤖 미국 기술주", "https://www.google.com/search?q=US+Tech+Stocks+News&tbm=nws")
with col_n4:
    st.link_button("💰 워렌버핏 포트폴리오", "https://www.google.com/search?q=Warren+Buffett+Portfolio+Update&tbm=nws")