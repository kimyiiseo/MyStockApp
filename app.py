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
st.title("📈 내 자산 관리 시스템 (Permission Fix)")

# ---------------------------------------------------------
# [구글 시트 연결]
# ---------------------------------------------------------
def get_google_sheet_client():
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            st.error("❌ Secrets 설정 오류")
            return None
            
        s = st.secrets["connections"]["gsheets"]
        
        # 줄바꿈 문자 수리
        raw_key = s.get("private_key", "")
        fixed_key = raw_key.replace("\\n", "\n")
        
        json_creds = {
            "type": s.get("type", "service_account"),
            "project_id": s.get("project_id"),
            "private_key_id": s.get("private_key_id"),
            "private_key": fixed_key,
            "client_email": s.get("client_email"),
            "client_id": s.get("client_id"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": s.get("client_x509_cert_url")
        }
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(json_creds, scopes=scopes)
        client = gspread.authorize(creds)
        
        spreadsheet_url = s.get("spreadsheet")
        sh = client.open_by_url(spreadsheet_url)
        return sh
        
    except Exception as e:
        # PermissionError가 뜨면 여기서 잡힙니다.
        if "403" in str(e) or "Permission" in str(e):
             st.error("🚨 **권한 오류 (PermissionError)**")
             st.info(f"👉 '{s.get('client_email')}' 이 주소를 구글 시트 [공유]에 추가하고 **[편집자]** 권한을 주세요.")
        else:
             st.error(f"❌ 연결 실패: {e}")
        return None

def load_data():
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("portfolio")
            data = worksheet.get_all_records()
            if not data: return pd.DataFrame([{"티커": "AAPL", "보유수량": 10.0, "목표비중(%)": 30}, {"티커": "TSLA", "보유수량": 5.0, "목표비중(%)": 30}])
            return pd.DataFrame(data)
        except gspread.exceptions.WorksheetNotFound:
            st.warning("⚠️ 'portfolio' 탭이 없습니다.")
            return pd.DataFrame()
        except: return pd.DataFrame()
    return pd.DataFrame()

def save_data(df):
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("portfolio")
            worksheet.clear()
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True # 성공하면 True 반환
        except Exception as e:
            st.error(f"저장 실패: {e}")
            return False # 실패하면 False
    return False

def load_history():
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("history")
            return pd.DataFrame(worksheet.get_all_records())
        except: return pd.DataFrame(columns=["날짜", "티커", "구분", "단가($)", "수량", "총액($)"])
    return pd.DataFrame()

def save_history(new_record_df):
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("history")
            for row in new_record_df.values.tolist(): worksheet.append_row(row)
        except: pass

# ---------------------------------------------------------
# [뉴스 & 시장 지표]
# ---------------------------------------------------------
def get_market_data():
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        treasury = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        nasdaq = yf.Ticker("^NDX").history(period="1d")['Close'].iloc[-1]
        return usd_krw, treasury, nasdaq
    except: return 0, 0, 0

def get_news_feed(query):
    try:
        clean_query = query.strip()
        encoded_query = urllib.parse.quote(clean_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        return feed.entries[:5] if feed.entries else []
    except: return []

# ---------------------------------------------------------
# [UI 구성]
# ---------------------------------------------------------
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
budget = monthly_investment + current_cash
st.sidebar.markdown(f"### 💼 가용 자금: **${budget:,.2f}**")

tab1, tab2, tab3, tab4 = st.tabs(["📊 리밸런싱", "📝 거래 기록", "📜 내역", "📰 뉴스"])

with tab1:
    st.markdown("### ⚖️ 포트폴리오")
    df = load_data()
    
    # 데이터가 없으면 빈 껍데기라도 만듦
    if df.empty:
        df = pd.DataFrame(columns=["티커", "보유수량", "목표비중(%)"])
        st.info("데이터를 불러오지 못했습니다. 위쪽 에러 메시지를 확인하세요.")

    edited_df = st.data_editor(df, num_rows="dynamic", key="portfolio_editor",
        column_config={
            "보유수량": st.column_config.NumberColumn(format="%.4f"),
            "목표비중(%)": st.column_config.NumberColumn(format="%d%%"),
        })
        
    if st.button("💾 구글 시트에 저장 및 분석"):
        with st.spinner('처리 중...'):
            # 저장 먼저 시도
            success = save_data(edited_df)
            
            if success: # 저장이 성공했을 때만 계산 시작! (NameError 방지)
                final_data = []
                for idx, row in edited_df.iterrows():
                    # 변수 초기화 (NameError 방지)
                    ticker = ""
                    qty = 0.0
                    tgt = 0.0
                    price = 0.0
                    
                    try:
                        ticker = row.get('티커', "")
                        if not ticker: continue # 티커 없으면 건너뜀
                        
                        qty = float(row.get('보유수량', 0)) if pd.notnull(row.get('보유수량')) else 0
                        tgt = float(row.get('목표비중(%)', 0)) if pd.notnull(row.get('목표비중(%)')) else 0
                        
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period="1d")
                        price = hist['Close'].iloc[-1] if not hist.empty else 0
                    except: 
                        price = 0
                    
                    # 모든 변수가 준비된 상태에서만 append
                    final_data.append({"티커": ticker, "보유수량": qty, "현재가($)": price, "현재평가액($)": price*qty, "목표비중(%)": tgt})
                
                res = pd.DataFrame(final_data)
                if not res.empty:
                    val = res['현재평가액($)'].sum()
                    sim = val + budget
                    res['이상적'] = sim * (res['목표비중(%)']/100)
                    res['부족'] = res['이상적'] - res['현재평가액($)']
                    
                    buy = res[(res['부족']>0) & (res['현재가($)']>0)].copy()
                    if not buy.empty:
                        need = buy['부족'].sum()
                        ratio = budget/need if (need>budget and need>0) else 1
                        buy['배정'] = buy['부족'] * ratio
                        buy['수량'] = buy['배정'] / buy['현재가($)']
                        st.success("🛒 매수 추천")
                        st.dataframe(buy[['티커', '현재가($)', '수량', '배정']].style.format({'현재가($)':'${:,.2f}', '수량':'{:.4f}', '배정':'${:,.2f}'}))
                    else: st.info("매수 없음")
                    
                    sell = res[(res['부족']<0) & (res['현재가($)']>0)].copy()
                    if not sell.empty:
                        sell['매도'] = sell['부족'].abs()
                        sell['수량'] = sell['매도'] / sell['현재가($)']
                        st.error("📉 매도 추천")
                        st.dataframe(sell[['티커', '현재가($)', '수량', '매도']].style.format({'현재가($)':'${:,.2f}', '수량':'{:.4f}', '매도':'${:,.2f}'}))
            else:
                st.error("⚠️ 데이터 저장을 실패해서 계산을 중단했습니다. 권한 설정을 먼저 해결해주세요.")

with tab2:
    st.markdown("### 📝 기록")
    pf = load_data()
    tickers = pf['티커'].tolist() if not pf.empty and '티커' in pf.columns else []
    with st.form("trade"):
        c1,c2,c3 = st.columns(3)
        ttype = c1.selectbox("구분", ["매수(Buy)", "매도(Sell)"])
        tdate = c1.date_input("날짜", datetime.today())
        tticker = c2.selectbox("종목", tickers)
        tprice = c2.number_input("단가", min_value=0.0)
        tqty = c3.number_input("수량", min_value=0.0, format="%.4f")
        if st.form_submit_button("✅ 저장"):
            if tprice>0 and tqty>0:
                if tticker in pf['티커'].values:
                    if ttype=="매수(Buy)": pf.loc[pf['티커']==tticker, '보유수량']+=tqty
                    else: pf.loc[pf['티커']==tticker, '보유수량']-=tqty
                    if save_data(pf):
                        save_history(pd.DataFrame([{"날짜":str(tdate), "티커":tticker, "구분":ttype, "단가($)":tprice, "수량":tqty, "총액($)":tprice*tqty}]))
                        st.success("완료!")
                        st.rerun()

with tab3:
    st.markdown("### 📜 내역")
    st.dataframe(load_history())

with tab4:
    st.markdown("### 📰 뉴스")
    target = st.text_input("검색어", "미국 증시")
    st.divider()
    try: items = get_news_feed(target)
    except: items = []
    if items:
        for i in items:
            with st.expander(f"📢 {i.title}"): st.write(f"[기사 보기]({i.link})")
    else: st.info(f"뉴스 없음")