import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os
import feedparser
import urllib.parse # [중요] 한글 URL을 변환해주는 도구 추가!
from datetime import datetime

# ---------------------------------------------------------
# [기본 설정]
# ---------------------------------------------------------
st.set_page_config(page_title="내 주식 파트너", layout="wide")
st.title("📈 내 자산 관리 시스템 (Final Fix)")

CSV_FILE = 'my_portfolio.csv'
HISTORY_FILE = 'trade_history.csv'

# ---------------------------------------------------------
# [함수 모음]
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

# [수정됨] 뉴스 가져오기 (한글 인코딩 추가)
def get_news_feed(query):
    # 한글 검색어를 URL용 외계어로 변환 (예: 미국증시 -> %EB%AF%B8...)
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    # 안전하게 뉴스 가져오기
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            return feed.entries[:5]
        else:
            return []
    except Exception as e:
        return []

# ---------------------------------------------------------
# [상단] 시장 지표
# ---------------------------------------------------------
st.markdown("### 🌍 실시간 시장 지표")
col_m1, col_m2, col_m3 = st.columns(3)
with st.spinner("지표 로딩 중..."):
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

st.sidebar.markdown(f"### 💼 총 가용 자금: **${available_budget:,.2f}**")
st.sidebar.info("💡 매도 후 생긴 현금은 '보유 예수금'에 입력하세요.")

# ---------------------------------------------------------
# [메인 화면] 탭 구성
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📊 리밸런싱", "📝 거래 기록", "📜 내역 조회", "📰 뉴스룸"])

# =========================================================
# [탭 1] 리밸런싱
# =========================================================
with tab1:
    st.markdown("### ⚖️ 포트폴리오 균형 맞추기")
    df = load_data()
    edited_df = st.data_editor(df, num_rows="dynamic", key="portfolio_editor",
        column_config={
            "보유수량": st.column_config.NumberColumn("보유수량", step=0.0001, format="%.4f"),
            "목표비중(%)": st.column_config.NumberColumn("목표비중(%)", min_value=0, max_value=100, format="%d%%"),
        }
    )

    if st.button("💾 저장 및 분석 시작", key="calc_btn"):
        edited_df.to_csv(CSV_FILE, index=False)
        with st.spinner('계산 중...'):
            final_data = []
            for index, row in edited_df.iterrows():
                ticker = row['티커']
                qty = float(row['보유수량']) if pd.notnull(row['보유수량']) else 0.0
                target_pct = float(row['목표비중(%)']) if pd.notnull(row['목표비중(%)']) else 0.0
                try:
                    stock = yf.Ticker(ticker)
                    history = stock.history(period="1d")
                    # [수정] 데이터가 없으면 확실하게 0 처리
                    if not history.empty:
                        current_price = history['Close'].iloc[-1]
                    else:
                        current_price = 0
                except: current_price = 0
                
                # 가격 오류 시 경고
                if current_price == 0:
                    st.toast(f"⚠️ {ticker} 가격을 가져오지 못했습니다. 계산에서 제외됩니다.")

                final_data.append({"티커": ticker, "보유수량": qty, "현재가($)": current_price, "현재평가액($)": current_price * qty, "목표비중(%)": target_pct})
            
            result_df = pd.DataFrame(final_data)
            
            if not result_df.empty:
                # [안전 장치] 가격이 0원인 종목은 제외하고 계산 (에러 방지!)
                valid_df = result_df[result_df['현재가($)'] > 0].copy()
                
                if valid_df.empty:
                    st.error("❌ 현재 가격을 가져올 수 있는 종목이 하나도 없습니다. 잠시 후 다시 시도해주세요.")
                else:
                    total_stock_value = valid_df['현재평가액($)'].sum()
                    simulated_total_asset = total_stock_value + available_budget
                    
                    # 원본 데이터프레임에 계산 결과 병합 (0원인 것도 표시하기 위해)
                    result_df['이상적_목표금액($)'] = simulated_total_asset * (result_df['목표비중(%)'] / 100)
                    result_df['부족한금액($)'] = result_df['이상적_목표금액($)'] - result_df['현재평가액($)']
                    
                    # 1. 매수 로직
                    buy_df = result_df[(result_df['부족한금액($)'] > 0) & (result_df['현재가($)'] > 0)].copy()
                    
                    if not buy_df.empty:
                        total_needed = buy_df['부족한금액($)'].sum()
                        # 예산 배분
                        if total_needed > available_budget:
                            ratio = available_budget / total_needed if total_needed > 0 else 0
                            buy_df['배정된_매수금액($)'] = buy_df['부족한금액($)'] * ratio
                        else:
                            buy_df['배정된_매수금액($)'] = buy_df['부족한금액($)']
                        
                        # [핵심] 0으로 나누기 방지
                        buy_df['추천_수량'] = buy_df.apply(lambda x: x['배정된_매수금액($)'] / x['현재가($)'] if x['현재가($)'] > 0 else 0, axis=1)

                    # 2. 매도 로직
                    sell_df = result_df[(result_df['부족한금액($)'] < 0) & (result_df['현재가($)'] > 0)].copy()
                    
                    if not sell_df.empty:
                        sell_df['매도해야할금액($)'] = sell_df['부족한금액($)'].abs()
                        sell_df['추천_수량'] = sell_df.apply(lambda x: x['매도해야할금액($)'] / x['현재가($)'] if x['현재가($)'] > 0 else 0, axis=1)

                    # 화면 출력
                    st.divider()
                    c1, c2 = st.columns(2)
                    with c1:
                        st.success("🛒 **매수(Buy) 추천**")
                        if not buy_df.empty:
                            st.dataframe(buy_df[['티커', '현재가($)', '추천_수량', '배정된_매수금액($)']].style.format({'현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '배정된_매수금액($)': '${:,.2f}'}))
                        else: st.info("매수 대상 없음")
                    with c2:
                        st.error("📉 **매도(Sell) 추천**")
                        if not sell_df.empty:
                            st.dataframe(sell_df[['티커', '현재가($)', '추천_수량', '매도해야할금액($)']].style.format({'현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '매도해야할금액($)': '${:,.2f}'}))
                        else: st.info("매도 대상 없음")

# =========================================================
# [탭 2] 거래 기록
# =========================================================
with tab2:
    st.markdown("### 📝 거래 기록 남기기")
    current_portfolio = load_data()
    ticker_list = current_portfolio['티커'].tolist()
    with st.form("trade_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            trade_type = st.selectbox("구분", ["매수(Buy)", "매도(Sell)"])
            date_input = st.date_input("날짜", datetime.today())
        with c2:
            ticker_input = st.selectbox("종목", ticker_list)
            price_input = st.number_input("단가 ($)", min_value=0.0, step=0.01)
        with c3:
            qty_input = st.number_input("수량", min_value=0.0, step=0.0001, format="%.4f")
        if st.form_submit_button("✅ 저장"):
            if price_input > 0 and qty_input > 0:
                if trade_type == "매수(Buy)":
                    current_portfolio.loc[current_portfolio['티커'] == ticker_input, '보유수량'] += qty_input
                    code = "매수"
                else:
                    current_portfolio.loc[current_portfolio['티커'] == ticker_input, '보유수량'] -= qty_input
                    code = "매도"
                current_portfolio.to_csv(CSV_FILE, index=False)
                
                history_df = load_history()
                new_record = pd.DataFrame([{"날짜": date_input, "티커": ticker_input, "구분": code, "단가($)": price_input, "수량": qty_input, "총액($)": price_input * qty_input}])
                history_df = pd.concat([new_record, history_df], ignore_index=True)
                history_df.to_csv(HISTORY_FILE, index=False)
                st.success("저장 완료!")
                st.rerun()

# =========================================================
# [탭 3] 내역 조회
# =========================================================
with tab3:
    st.markdown("### 📜 거래 내역")
    st.dataframe(load_history())

# =========================================================
# [탭 4] 뉴스룸 (한글 오류 해결!)
# =========================================================
with tab4:
    st.markdown("### 📰 실시간 맞춤 뉴스")
    
    keywords = ["미국 증시", "연준 금리", "나스닥 전망", "엔비디아", "테슬라"]
    cols = st.columns(len(keywords))
    
    for i, keyword in enumerate(keywords):
        with cols[i]:
            if st.button(f"#{keyword}", key=f"news_{i}"):
                st.session_state['selected_news'] = keyword

    if 'selected_news' not in st.session_state:
        st.session_state['selected_news'] = "미국 증시"

    target_keyword = st.session_state['selected_news']
    st.divider()
    st.subheader(f"🔍 '{target_keyword}' 관련 최신 뉴스")
    
    with st.spinner('뉴스를 불러오는 중...'):
        # 여기서 아까 만든 안전한 함수를 호출합니다
        news_items = get_news_feed(target_keyword)
        
        if news_items:
            for item in news_items:
                with st.expander(f"📢 {item.title}"):
                    st.markdown(f"**발행일:** {item.get('published', '날짜 정보 없음')}")
                    st.markdown(f"[기사 원문 읽기 (클릭)]({item.link})")
        else:
            st.info("뉴스를 가져오지 못했습니다. 잠시 후 다시 시도해주세요.")