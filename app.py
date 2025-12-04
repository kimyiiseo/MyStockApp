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
st.title("📈 내 자산 관리 시스템 (Final)")

# ---------------------------------------------------------
# [구글 시트 연결]
# ---------------------------------------------------------
def get_google_sheet_client():
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            st.error("❌ Secrets 설정 오류")
            return None
        
        s = st.secrets["connections"]["gsheets"]
        
        # 키 줄바꿈 수리 (혹시 모를 에러 방지)
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
        st.error(f"❌ 연결 오류: {e}")
        return None

def load_data():
    sh = get_google_sheet_client()
    if sh:
        try:
            worksheet = sh.worksheet("portfolio")
            data = worksheet.get_all_records()
            # 데이터가 비어있으면 기본값 리턴
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
            return True
        except Exception as e:
            st.error(f"저장 실패: {e}")
            return False
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
        encoded = urllib.parse.quote(query.strip())
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
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
budget = st.sidebar.number_input("➕ 추가 투자금($)", value=340.0) + st.sidebar.number_input("💵 예수금($)", value=0.0)
st.sidebar.markdown(f"### 💼 가용 자금: **${budget:,.2f}**")
st.sidebar.success("✅ 구글 시트 연결됨")

tab1, tab2, tab3, tab4 = st.tabs(["📊 리밸런싱", "📝 거래 기록", "📜 내역", "📰 뉴스"])

with tab1:
    st.markdown("### ⚖️ 포트폴리오")
    df = load_data()
    if df.empty: 
        st.info("데이터를 불러오는 중입니다...")
        df = pd.DataFrame(columns=["티커", "보유수량", "목표비중(%)"])
        
    edited_df = st.data_editor(df, num_rows="dynamic", key="portfolio_editor",
        column_config={
            "보유수량": st.column