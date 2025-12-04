import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import feedparser
import urllib.parse
from datetime import datetime
from streamlit_gsheets import GSheetsConnection # 구글 시트 연결 도구

# ---------------------------------------------------------
# [기본 설정]
# ---------------------------------------------------------
st.set_page_config(page_title="내 주식 파트너", layout="wide")
st.title("📈 내 자산 관리 시스템 (Google Sheets Ver.)")

# ---------------------------------------------------------
# [데이터베이스 함수: 구글 시트]
# ---------------------------------------------------------
# 연결 객체 생성 (Secrets에 입력한 정보를 자동으로 가져옵니다)
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # 'portfolio' 라는 이름의 탭(워크시트)을 읽어옵니다.
        df = conn.read(worksheet="portfolio", ttl="0") # ttl=0은 캐시 끄기(항상 최신본 가져오기)
        # 만약 비어있거나 필수 컬럼이 없으면 기본값 생성
        if df.empty or '티커' not in df.columns:
             raise ValueError("데이터 없음")
        return df
    except:
        # 시트가 비어있을 때 기본 데이터
        default_data = [
            {"티커": "AAPL", "보유수량": 10.0, "목표비중(%)": 30},
            {"티커": "TSLA", "보유수량": 5.0, "목표비중(%)": 30},
            {"티커": "NVDA", "보유수량": 2.0, "목표비중(%)": 20},
            {"티커": "SCHD", "보유수량": 10.0, "목표비중(%)": 20},
        ]
        return pd.DataFrame(default_data)

def save_data(df):
    # 'portfolio' 탭에 데이터프레임을 덮어씁니다.
    conn.update(worksheet="portfolio", data=df)

def load_history():
    try:
        df = conn.read(worksheet="history", ttl="0")
        if df.empty or '날짜' not in df.columns:
             raise ValueError("데이터 없음")
        return df
    except:
        return pd.DataFrame(columns=["날짜", "티커", "구분", "단가($)", "수량", "총액($)"])

def save_history(new_record_df):
    # 기존 기록을 가져와서 합친 뒤 저장
    old_df = load_history()
    updated_df = pd.concat([new_record_df, old_df], ignore_index=True)
    conn.update(worksheet="history", data=updated_df)

# ---------------------------------------------------------
# [시장 지표 및 뉴스 함수]
# ---------------------------------------------------------
def get_market_data():
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        treasury = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        nasdaq = yf.Ticker("^NDX").history(period="1d")['Close'].iloc[-1]
        return usd_krw, treasury, nasdaq
    except:
        return 0, 0, 0

def get_news_feed(query):
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(rss_url)
        return feed.entries[:5] if feed.entries else []
    except:
        return []

# ---------------------------------------------------------
# [메인 화면 로직]
# ---------------------------------------------------------
st.markdown("### 🌍 실시간 시장 지표")
col_m1, col_m2, col_m3 = st.columns(3)
with st.spinner("지표 로딩 중..."):
    rate, bond, ndx = get_market_data()
with col_m1: st.metric("🇺🇸 원/달러 환율", f"{rate:,.2f} 원")
with col_m2: st.metric("🏦 미국 10년물 금리", f"{bond:,.2f} %")
with col_m3: st.metric("💻 나스닥 100", f"{ndx:,.2f}")
st.divider()

st.sidebar.header("💰 자산 설정")
monthly_investment = st.sidebar.number_input("➕ 이번 달 추가 투자금 ($)", value=340.0, step=10.0)
current_cash = st.sidebar.number_input("💵 현재 보유 예수금 ($)", value=0.0, step=10.0)
available_budget = monthly_investment + current_cash
st.sidebar.markdown(f"### 💼 총 가용 자금: **${available_budget:,.2f}**")
st.sidebar.success("✅ 구글 시트와 연동되어 데이터가 영구 저장됩니다.")

tab1, tab2, tab3, tab4 = st.tabs(["📊 리밸런싱", "📝 거래 기록", "📜 내역 조회", "📰 뉴스룸"])

# --- [탭 1] 리밸런싱 ---
with tab1:
    st.markdown("### ⚖️ 포트폴리오 균형 맞추기")
    df = load_data()
    edited_df = st.data_editor(df, num_rows="dynamic", key="portfolio_editor",
        column_config={
            "보유수량": st.column_config.NumberColumn("보유수량", step=0.0001, format="%.4f"),
            "목표비중(%)": st.column_config.NumberColumn("목표비중(%)", min_value=0, max_value=100, format="%d%%"),
        }
    )

    if st.button("💾 구글 시트에 저장 및 분석", key="calc_btn"):
        with st.spinner('구글 시트에 저장하고 계산 중...'):
            save_data(edited_df) # 구글 시트 저장
            
            final_data = []
            for index, row in edited_df.iterrows():
                ticker = row['티커']
                qty = float(row['보유수량']) if pd.notnull(row['보유수량']) else 0.0
                target_pct = float(row['목표비중(%)']) if pd.notnull(row['목표비중(%)']) else 0.0
                try:
                    stock = yf.Ticker(ticker)
                    history = stock.history(period="1d")
                    current_price = history['Close'].iloc[-1] if not history.empty else 0
                except: current_price = 0
                
                final_data.append({"티커": ticker, "보유수량": qty, "현재가($)": current_price, "현재평가액($)": current_price * qty, "목표비중(%)": target_pct})
            
            result_df = pd.DataFrame(final_data)
            if not result_df.empty:
                valid_df = result_df[result_df['현재가($)'] > 0].copy()
                if valid_df.empty:
                    st.error("❌ 현재 가격 조회 실패")
                else:
                    total_stock_value = valid_df['현재평가액($)'].sum()
                    simulated_total_asset = total_stock_value + available_budget
                    result_df['이상적_목표금액($)'] = simulated_total_asset * (result_df['목표비중(%)'] / 100)
                    result_df['부족한금액($)'] = result_df['이상적_목표금액($)'] - result_df['현재평가액($)']
                    
                    buy_df = result_df[(result_df['부족한금액($)'] > 0) & (result_df['현재가($)'] > 0)].copy()
                    if not buy_df.empty:
                        total_needed = buy_df['부족한금액($)'].sum()
                        ratio = available_budget / total_needed if (total_needed > available_budget and total_needed > 0) else 1
                        buy_df['배정된_매수금액($)'] = buy_df['부족한금액($)'] * ratio
                        buy_df['추천_수량'] = buy_df.apply(lambda x: x['배정된_매수금액($)'] / x['현재가($)'], axis=1)

                    sell_df = result_df[(result_df['부족한금액($)'] < 0) & (result_df['현재가($)'] > 0)].copy()
                    if not sell_df.empty:
                        sell_df['매도해야할금액($)'] = sell_df['부족한금액($)'].abs()
                        sell_df['추천_수량'] = sell_df.apply(lambda x: x['매도해야할금액($)'] / x['현재가($)'], axis=1)

                    st.divider()
                    c1, c2 = st.columns(2)
                    with c1:
                        st.success("🛒 **매수(Buy) 추천**")
                        if not buy_df.empty:
                            st.dataframe(buy_df[['티커', '현재가($)', '추천_수량', '배정된_매수금액($)']].style.format({'현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '배정된_매수금액($)': '${:,.2f}'}))
                        else: st.info("대상 없음")
                    with c2:
                        st.error("📉 **매도(Sell) 추천**")
                        if not sell_df.empty:
                            st.dataframe(sell_df[['티커', '현재가($)', '추천_수량', '매도해야할금액($)']].style.format({'현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '매도해야할금액($)': '${:,.2f}'}))
                        else: st.info("대상 없음")

# --- [탭 2] 거래 기록 ---
with tab2:
    st.markdown("### 📝 거래 기록 (구글 시트 저장)")
    current_portfolio = load_data()
    ticker_list = current_portfolio['티커'].tolist() if not current_portfolio.empty else []
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
                with st.spinner('기록 중...'):
                    # 1. 포트폴리오 수량 업데이트
                    if ticker_input in current_portfolio['티커'].values:
                        if trade_type == "매수(Buy)":
                            current_portfolio.loc[current_portfolio['티커'] == ticker_input, '보유수량'] += qty_input
                        else:
                            current_portfolio.loc[current_portfolio['티커'] == ticker_input, '보유수량'] -= qty_input
                        save_data(current_portfolio) # 포트폴리오 저장
                        
                        # 2. 거래 내역 저장
                        new_record = pd.DataFrame([{"날짜": str(date_input), "티커": ticker_input, "구분": trade_type, "단가($)": price_input, "수량": qty_input, "총액($)": price_input * qty_input}])
                        save_history(new_record) # 내역 저장
                        
                        st.success("구글 시트에 저장 완료!")
                        st.rerun()
                    else:
                        st.error("종목을 찾을 수 없습니다.")

# --- [탭 3] 내역 조회 ---
with tab3:
    st.markdown("### 📜 거래 내역")
    st.dataframe(load_history())

# --- [탭 4] 뉴스룸 ---
with tab4:
    st.markdown("### 📰 뉴스룸")
    keywords = ["미국 증시", "연준 금리", "나스닥", "엔비디아", "테슬라"]
    cols = st.columns(len(keywords))
    for i, kw in enumerate(keywords):
        if cols[i].button(f"#{kw}"): st.session_state['selected_news'] = kw
    
    target = st.session_state.get('selected_news', "미국 증시")
    st.divider()
    st.subheader(f"🔍 {target}")
    items = get_news_feed(target)
    if items:
        for item in items:
            with st.expander(f"📢 {item.title}"):
                st.write(f"[기사 보기]({item.link})")
    else:
        st.info("뉴스 없음")