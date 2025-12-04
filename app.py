import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import feedparser
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ---------------------------------------------------------
# [기본 설정]
# ---------------------------------------------------------
st.set_page_config(page_title="내 주식 파트너", layout="wide")
st.title("📈 내 자산 관리 시스템 (Final Safe Mode)")

# ---------------------------------------------------------
# [구글 시트 연결: JSON 파싱 없는 안전 모드]
# ---------------------------------------------------------
def get_google_sheet_client():
    try:
        # Secrets에서 값들을 직접 가져와서 딕셔너리로 조립합니다.
        # (json.loads를 쓰지 않으므로 'Invalid control character' 에러가 날 수 없습니다)
        s = st.secrets["connections"]["gsheets"]
        
        json_creds = {
            "type": s["type"],
            "project_id": s["project_id"],
            "private_key_id": s["private_key_id"],
            "private_key": s["private_key"],
            "client_email": s["client_email"],
            "client_id": s["client_id"],
            "auth_uri": s["auth_uri"],
            "token_uri": s["token_uri"],
            "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
            "client_x509_cert_url": s["client_x509_cert_url"]
        }
        
        # 인증 범위 설정
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 연결
        creds = Credentials.from_service_account_info(json_creds, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 시트 열기
        spreadsheet_url = s["spreadsheet"]
        sh = client.open_by_url(spreadsheet_url)
        return sh
        
    except Exception as e:
        st.error(f"❌ 구글 시트 연결 실패: {e}")
        st.info("💡 Secrets 설정에서 'private_key'나 'client_email'이 정확한지 확인해주세요.")
        return None

# 데이터 불러오기
def load_data():
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("portfolio")
            data = worksheet.get_all_records()
            if not data:
                return pd.DataFrame([
                    {"티커": "AAPL", "보유수량": 10.0, "목표비중(%)": 30},
                    {"티커": "TSLA", "보유수량": 5.0, "목표비중(%)": 30},
                ])
            return pd.DataFrame(data)
        except gspread.exceptions.WorksheetNotFound:
            st.error("'portfolio' 탭이 없습니다. 시트 아래쪽 탭 이름을 확인하세요.")
            return pd.DataFrame()
        except:
            return pd.DataFrame([
                    {"티커": "AAPL", "보유수량": 10.0, "목표비중(%)": 30},
            ])
    return pd.DataFrame()

# 데이터 저장
def save_data(df):
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("portfolio")
            worksheet.clear()
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        except Exception as e:
            st.error(f"저장 실패: {e}")

# 기록 불러오기
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

# 기록 저장
def save_history(new_record_df):
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("history")
            for row in new_record_df.values.tolist():
                worksheet.append_row(row)
        except Exception as e:
            st.error(f"기록 실패: {e}")

# ---------------------------------------------------------
# [나머지 기능들]
# ---------------------------------------------------------
def get_market_data():
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        treasury = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        nasdaq = yf.Ticker("^NDX").history(period="1d")['Close'].iloc[-1]
        return usd_krw, treasury, nasdaq
    except: return 0, 0, 0

def get_news_feed(query):
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(rss_url)
        return feed.entries[:5] if feed.entries else []
    except: return []

st.markdown("### 🌍 실시간 시장 지표")
c1, c2, c3 = st.columns(3)
with st.spinner("로딩 중..."):
    rate, bond, ndx = get_market_data()
with c1: st.metric("🇺🇸 환율", f"{rate:,.2f} 원")
with c2: st.metric("🏦 금리", f"{bond:,.2f} %")
with c3: st.metric("💻 나스닥", f"{ndx:,.2f}")
st.divider()

st.sidebar.header("💰 자산 설정")
monthly_investment = st.sidebar.number_input("➕ 추가 투자금 ($)", value=340.0, step=10.0)
current_cash = st.sidebar.number_input("💵 보유 예수금 ($)", value=0.0, step=10.0)
available_budget = monthly_investment + current_cash
st.sidebar.markdown(f"### 💼 가용 자금: **${available_budget:,.2f}**")
st.sidebar.success("✅ 안전 연결 모드")

tab1, tab2, tab3, tab4 = st.tabs(["📊 리밸런싱", "📝 거래 기록", "📜 내역", "📰 뉴스"])

with tab1:
    st.markdown("###⚖️ 포트폴리오")
    df = load_data()
    if not df.empty:
        edited_df = st.data_editor(df, num_rows="dynamic", key="portfolio_editor",
            column_config={
                "보유수량": st.column_config.NumberColumn("보유수량", step=0.0001, format="%.4f"),
                "목표비중(%)": st.column_config.NumberColumn("목표비중(%)", min_value=0, max_value=100, format="%d%%"),
            })
        if st.button("💾 구글 시트에 저장 및 분석", key="calc_btn"):
            with st.spinner('처리 중...'):
                save_data(edited_df)
                final_data = []
                for index, row in edited_df.iterrows():
                    ticker = row['티커']
                    qty = float(row['보유수량']) if pd.notnull(row['보유수량']) else 0.0
                    target_pct = float(row['목표비중(%)']) if pd.notnull(row['목표비중(%)']) else 0.0
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period="1d")
                        price = hist['Close'].iloc[-1] if not hist.empty else 0
                    except: price = 0
                    final_data.append({"티커": ticker, "보유수량": qty, "현재가($)": price, "현재평가액($)": price * qty, "목표비중(%)": target_pct})
                result_df = pd.DataFrame(final_data)
                if not result_df.empty:
                    valid_df = result_df[result_df['현재가($)'] > 0].copy()
                    if valid_df.empty: st.error("가격 조회 실패")
                    else:
                        total_val = valid_df['현재평가액($)'].sum()
                        sim_total = total_val + available_budget
                        result_df['이상적_목표금액($)'] = sim_total * (result_df['목표비중(%)'] / 100)
                        result_df['부족한금액($)'] = result_df['이상적_목표금액($)'] - result_df['현재평가액($)']
                        
                        buy_df = result_df[(result_df['부족한금액($)'] > 0) & (result_df['현재가($)'] > 0)].copy()
                        if not buy_df.empty:
                            needed = buy_df['부족한금액($)'].sum()
                            ratio = available_budget / needed if (needed > available_budget and needed > 0) else 1
                            buy_df['배정된_매수금액($)'] = buy_df['부족한금액($)'] * ratio
                            buy_df['추천_수량'] = buy_df.apply(lambda x: x['배정된_매수금액($)'] / x['현재가($)'], axis=1)

                        sell_df = result_df[(result_df['부족한금액($)'] < 0) & (result_df['현재가($)'] > 0)].copy()
                        if not sell_df.empty:
                            sell_df['매도해야할금액($)'] = sell_df['부족한금액($)'].abs()
                            sell_df['추천_수량'] = sell_df.apply(lambda x: x['매도해야할금액($)'] / x['현재가($)'], axis=1)

                        st.divider()
                        c1, c2 = st.columns(2)
                        with c1:
                            st.success("🛒 **매수 추천**")
                            if not buy_df.empty: st.dataframe(buy_df[['티커', '현재가($)', '추천_수량', '배정된_매수금액($)']].style.format({'현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '배정된_매수금액($)': '${:,.2f}'}))
                        with c2:
                            st.error("📉 **매도 추천**")
                            if not sell_df.empty: st.dataframe(sell_df[['티커', '현재가($)', '추천_수량', '매도해야할금액($)']].style.format({'현재가($)': '${:,.2f}', '추천_수량': '{:.4f}', '매도해야할금액($)': '${:,.2f}'}))

with tab2:
    st.markdown("### 📝 거래 기록")
    curr_pf = load_data()
    tickers = curr_pf['티커'].tolist() if not curr_pf.empty else []
    with st.form("trade"):
        c1, c2, c3 = st.columns(3)
        with c1:
            ttype = st.selectbox("구분", ["매수(Buy)", "매도(Sell)"])
            tdate = st.date_input("날짜", datetime.today())
        with c2:
            tticker = st.selectbox("종목", tickers)
            tprice = st.number_input("단가", min_value=0.0, step=0.01)
        with c3:
            tqty = st.number_input("수량", min_value=0.0, step=0.0001, format="%.4f")
        if st.form_submit_button("✅ 저장"):
            if tprice > 0 and tqty > 0:
                with st.spinner('저장 중...'):
                    if tticker in curr_pf['티커'].values:
                        if ttype == "매수(Buy)": curr_pf.loc[curr_pf['티커'] == tticker, '보유수량'] += tqty
                        else: curr_pf.loc[curr_pf['티커'] == tticker, '보유수량'] -= tqty
                        save_data(curr_pf)
                        new_rec = pd.DataFrame([{"날짜": str(tdate), "티커": tticker, "구분": ttype, "단가($)": tprice, "수량": tqty, "총액($)": tprice * tqty}])
                        save_history(new_rec)
                        st.success("완료!")
                        st.rerun()

with tab3:
    st.markdown("### 📜 내역")
    st.dataframe(load_history())

with tab4:
    st.markdown("### 📰 뉴스")
    keywords = ["미국 증시", "연준 금리", "나스닥", "엔비디아", "테슬라"]
    cols = st.columns(len(keywords))
    for i, kw in enumerate(keywords):
        if cols[i].button(f"#{kw}"): st.session_state['news'] = kw
    target = st.session_state.get('news', "미국 증시")
    st.divider()
    st.subheader(f"🔍 {target}")
    items = get_news_feed(target)
    if items:
        for item in items:
            with st.expander(f"📢 {item.title}"): st.write(f"[기사 보기]({item.link})")
    else: st.info("뉴스 없음")