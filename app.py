import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="최종 디버깅", layout="wide")
st.title("💣 연결 상태 정밀 해부")

st.write("### 1단계: Secrets 파일 해부")

# 1. Secrets가 존재하는지 확인
if "connections" not in st.secrets:
    st.error("❌ [connections] 섹션이 Secrets에 없습니다.")
    st.stop()

if "gsheets" not in st.secrets["connections"]:
    st.error("❌ [connections.gsheets] 섹션이 없습니다.")
    st.stop()

s = st.secrets["connections"]["gsheets"]
st.success("✅ Secrets 파일 구조는 정상입니다.")

# 2. 필수 데이터가 들어있는지 확인 (내용은 보안상 안 보여줌)
required_keys = ["type", "project_id", "private_key_id", "private_key", "client_email", "spreadsheet"]
missing_keys = [k for k in required_keys if k not in s]

if missing_keys:
    st.error(f"❌ 다음 항목이 Secrets에 빠져있습니다: {missing_keys}")
    st.stop()
else:
    st.success("✅ 필수 항목들이 모두 존재합니다.")

# 3. 데이터 내용 살짝 검증
st.write(f"- **이메일:** `{s['client_email']}`")
st.write(f"- **시트 주소:** `{s['spreadsheet']}`")
pk_len = len(s['private_key'])
st.write(f"- **비밀키 길이:** {pk_len}글자 (정상이라면 1500자 이상이어야 함)")

if pk_len < 100:
    st.error("❌ 비밀키(private_key)가 너무 짧습니다! 복사가 잘못된 것 같습니다.")
    st.stop()

# ---------------------------------------------------------
# [여기서부터 안전장치 없이 연결 시도]
# ---------------------------------------------------------
st.write("### 2단계: 구글 서버 접속 시도 (에러나면 여기서 터집니다)")

# 키 줄바꿈 처리
raw_key = s["private_key"]
fixed_key = raw_key.replace("\\n", "\n")

json_creds = {
    "type": s["type"],
    "project_id": s["project_id"],
    "private_key_id": s["private_key_id"],
    "private_key": fixed_key,
    "client_email": s["client_email"],
    "client_id": s.get("client_id"), # 없으면 None
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": s.get("client_x509_cert_url")
}

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# 1. 인증 객체 만들기
st.text("creating credentials...")
creds = Credentials.from_service_account_info(json_creds, scopes=scopes)

# 2. 클라이언트 로그인
st.text("authorizing client...")
client = gspread.authorize(creds)
st.success("✅ 구글 로그인 성공!")

# 3. 시트 열기
st.text(f"opening spreadsheet: {s['spreadsheet']}...")
sh = client.open_by_url(s["spreadsheet"])

st.success(f"🎉 **연결 대성공!** 시트 이름: {sh.title}")

# 4. 탭 확인
st.text("checking worksheets...")
ws_list = sh.worksheets()
st.write(f"발견된 탭 목록: {[w.title for w in ws_list]}")

if "portfolio" in [w.title for w in ws_list]:
    st.balloons()
    st.success("모든 테스트 통과! 이제 원래 코드로 돌아가셔도 됩니다.")
else:
    st.error("❌ 연결은 됐는데 'portfolio' 탭이 없습니다! 탭 이름을 확인하세요.")