import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import feedparser
import urllib.parse
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ---------------------------------------------------------
# [기본 설정]
# ---------------------------------------------------------
st.set_page_config(page_title="내 주식 파트너", layout="wide")
st.title("📈 내 자산 관리 시스템 (Direct Connection)")

# ---------------------------------------------------------
# [구글 시트 연결: 직접 연결 방식]
# ---------------------------------------------------------
# 이 방식은 에러가 날 확률이 거의 없습니다.
def get_google_sheet_client():
    try:
        # Secrets에서 정보 가져오기
        secrets = st.secrets["connections"]["gsheets"]
        
        # JSON 문자열을 파이썬 객체로 변환
        json_creds = json.loads(secrets["service_account"])
        
        # 인증 범위 설정
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 자격 증명 생성 및 클라이언트 연결
        creds = Credentials.from_service_account_info(json_creds, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 시트 열기
        spreadsheet_url = secrets["spreadsheet"]
        sh = client.open_by_url(spreadsheet_url)
        return sh
    except Exception as e:
        st.error(f"❌ 구글 시트 연결 실패: {e}")
        return None

# 데이터 불러오기 함수
def load_data():
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("portfolio")
            data = worksheet.get_all_records()
            if not data:
                # 데이터가 없으면 기본값 반환
                return pd.DataFrame([
                    {"티커": "AAPL", "보유수량": 10.0, "목표비중(%)": 30},
                    {"티커": "TSLA", "보유수량": 5.0, "목표비중(%)": 30},
                ])
            return pd.DataFrame(data)
        except gspread.exceptions.WorksheetNotFound:
            st.error("'portfolio' 탭을 찾을 수 없습니다.")
            return pd.DataFrame()
    return pd.DataFrame()

# 데이터 저장 함수
def save_data(df):
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("portfolio")
            # 헤더와 데이터를 리스트 형태로 변환하여 업로드
            worksheet.clear() # 기존 내용 지우기
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")

# 거래 기록 불러오기
def load_history():
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("history")
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except:
            return pd.DataFrame(columns=["날짜", "티커", "구분", "단가($)", "수량", "총액($)"])
    return pd.DataFrame()

# 거래 기록 저장하기
def save_history(new_record_df):
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("history")
            # 기존 데이터 끝에 추가 (append_row 사용)
            for row in new_record_df.values.tolist():
                worksheet.append_row(row)
        except Exception as e:
            st.error(f"기록 저장 실패: {e}")

# ---------------------------------------------------------
# [시장 지표 및 뉴스]
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
    # [수정] 한글 인코딩 문제를 완벽하게 해결
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
st.sidebar.success("✅ 구글 시트 직접 연결 모드 (안정성 강화)")

tab1, tab2, tab3, tab4 = st.tabs(["📊 리밸런싱", "📝 거래 기록", "📜 내역 조회", "📰 뉴스룸"])

# --- [탭 1] 리밸런싱 ---
with tab1:
    st.markdown("### ⚖️ 포트폴리오 균형 맞추기")
    # 데이터 로드 시도
    df = load_data()
    
    if not df.empty:
        edited_df = st.data_editor(df, num_rows="dynamic", key="portfolio_editor",
            column_config={
                "보유수량": st.column_config.NumberColumn("보유수량", step=0.0001, format="%.4f"),
                "목표비중(%)": st.column_config.NumberColumn("목표비중(%)", min_value=0, max_value=100, format="%d%%"),
            }
        )

        if st.button("💾 구글 시트에 저장 및 분석", key="calc_btn"):
            with st.spinner('저장 및 계산 중...'):
                save_data(edited_df) # 저장 먼저 실행
                
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
                        st.error("❌ 현재 가격 조회 실패 (모든 종목 가격 0)")
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
    else:
        st.warning("구글 시트 'portfolio' 탭을 읽을 수 없습니다. 시트 권한을 확인해주세요.")

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
                        
                        save_data(current_portfolio) # 변경된 포트폴리오 저장
                        
                        # 2. 거래 내역 저장 (데이터프레임 생성 후 리스트로 변환하여 저장)
                        # 날짜를 문자열로 변환하여 JSON 직렬화 문제 방지
                        new_record = pd.DataFrame([{"날짜": str(date_input), "티커": ticker_input, "구분": trade_type, "단가($)": price_input, "수량": qty_input, "총액($)": price_input * qty_input}])
                        save_history(new_record) 
                        
                        st.success("구글 시트에 저장 완료!")
                        st.rerun()
                    else:
                        st.error("종목을 찾을 수 없습니다.")

# --- [탭 3] 내역 조회 ---
with tab3:
    st.markdown("### 📜 거래 내역")
    history_df = load_history()
    if not history_df.empty:
        st.dataframe(history_df)
    else:
        st.info("기록이 없습니다.")

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
    
    # [수정] 수정된 함수 호출
    items = get_news_feed(target)
    if items:
        for item in items:
            with st.expander(f"📢 {item.title}"):
                st.write(f"[기사 보기]({item.link})")
    else:
        st.info("뉴스 없음 (또는 로딩 실패)")