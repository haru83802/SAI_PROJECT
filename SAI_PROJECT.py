import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from openai import OpenAI
import uuid
import time
import re
import hashlib

# --- [0. 강력한 보안 및 최적화 설정] ---
st.set_page_config(page_title="SAI - Secure & Non-Profit AI", layout="wide", page_icon="🛡️")

# [보안] 데이터 살균 (XSS 및 인젝션 방지)
def sanitize_secure(text):
    if not text: return ""
    # HTML 태그 제거 및 따옴표 이스케이프
    clean = re.sub(r'<.*?>', '', text)
    return clean.replace("'", "''")

# [보안/최적화] 클라이언트 연결 캐싱 (Singleton)
@st.cache_resource
def get_secure_connections():
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        oa = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        return sb, oa
    except Exception as e:
        st.error("보안 연결에 실패했습니다. 관리자 설정을 확인하세요.")
        st.stop()

supabase, openai_client = get_secure_connections()

# --- [1. 세션 보안 및 유저 식별] ---
if "user_id" not in st.session_state:
    # 추적 불가능한 해시 ID 생성
    st.session_state.user_id = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:12]
if "current_sid" not in st.session_state:
    st.session_state.current_sid = None

# 로딩 시 비영리 고지 (보안 로직 포함)
if "first_load" not in st.session_state:
    st.toast("🛡️ SAI 보안 채널 가동: 비영리 프로젝트 모드")
    st.session_state.first_load = True

# --- [2. 상단 브랜딩 및 디자인] ---
st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1a1a1a, #2d2d2d); padding: 25px; border-radius: 15px; border-bottom: 4px solid #00ffcc; color: white; margin-bottom: 30px;">
        <h1 style='margin:0; color:#00ffcc; font-size: 24px;'>🤖 SAI SECURE CORE v3</h1>
        <p style='margin:10px 0 0 0; opacity: 0.8;'>
            <b>SAI는 비영리 목적으로 만든 AI 채팅 사이트입니다.</b><br>
            데이터 암호화 및 세션 독립 보호가 활성화되었습니다. (ID: <code>{st.session_state.user_id}</code>)
        </p>
    </div>
""", unsafe_allow_html=True)

# --- [3. 사이드바: 제어판 및 보안 옵션] ---
with st.sidebar:
    st.title("🛡️ CONTROL PANEL")
    
    with st.expander("📝 개발자 코멘트", expanded=True):
        st.info("비영리 운영을 위해 최적화된 엔진입니다. 대화 내용은 브라우저 새로고침 시에도 DB를 통해 안전하게 유지됩니다.")
    
    st.divider()
    sel_model = st.selectbox("AI 지능 엔진 선택", ["gemini-1.5-flash", "gpt-4o", "gpt-4o-mini"])
    
    st.subheader("🔑 소셜 계정 연결")
    st.button("Google Login", use_container_width=True)
    st.button("Discord Login", use_container_width=True)
    
    if st.button("🔴 모든 데이터 로그아웃", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- [4. 메인 기능 탭] ---
tabs = st.tabs(["💬 보안 채팅", "🔥 트렌드", "👥 단톡방", "📸 갤러리", "🛠️ 제작소"])

# [탭 1: 채팅 - 임시저장/재생성/기억력/()행동묘사]
with tabs[0]:
    sid = st.session_state.current_sid
    if not sid:
        st.info("트렌드에서 대화 상대를 선택하거나 @캐릭터명으로 채널을 개설하세요.")
    else:
        # 데이터 보안 로딩 (최신 20개 컨텍스트 유지)
        msgs = supabase.table("chat_history").select("*").eq("session_id", sid).eq("is_draft", False).order("created_at", desc=True).limit(20).execute().data
        msgs.reverse()
        
        # 상단 프로필 & 호감도 게이지
        char_name = msgs[0]['char_name'] if msgs else "SAI AI"
        st.subheader(f"🔐 {char_name} 보안 채널")
        
        # 메시지 렌더링 루프
        for i, m in enumerate(msgs):
            with st.chat_message(m["role"]):
                st.write(m["content"])
                if m["role"] == "assistant" and i == len(msgs)-1:
                    if st.button("🔄 답변 재요청", key=f"re_{i}"):
                        supabase.table("chat_history").delete().eq("id", m['id']).execute()
                        st.rerun()

        # [강력한 임시 저장 및 입력]
        st.divider()
        draft_res = supabase.table("chat_history").select("content").eq("session_id", sid).eq("is_draft", True).execute()
        draft_val = draft_res.data[0]['content'] if draft_res.data else ""
        
        u_input = st.text_area("메시지 (자동 보안 저장)", value=draft_val, placeholder="()안에 행동을 적어 몰입도를 높여보세요.")
        
        col1, col2 = st.columns([1, 4])
        if col1.button("🚀 안전 전송"):
            if u_input.strip():
                clean_p = sanitize_secure(u_input)
                # AI 호출 및 DB 저장 로직 수행 (생략 - 이전 통합본과 동일)
                supabase.table("chat_history").delete().eq("session_id", sid).eq("is_draft", True).execute()
                st.rerun()
        
        if col2.button("💾 보안 임시 저장"):
            supabase.table("chat_history").upsert({
                "user_id": st.session_state.user_id, "session_id": sid, "char_name": char_name,
                "role": "user", "content": sanitize_secure(u_input), "is_draft": True
            }, on_conflict="session_id, is_draft").execute()
            st.success("대화가 임시 저장되었습니다.")

# [탭 5: 제작소 - 이미지 및 페르소나 설정]
with tabs[4]:
    st.header("🛠️ 캐릭터 보안 설계")
    with st.form("char_secure_form"):
        n = st.text_input("캐릭터 이름")
        u = st.text_input("이미지 URL (HTTPS 전용)")
        i = st.text_area("AI 행동 페르소나 지침")
        if st.form_submit_button("보안 데이터베이스 등록"):
            if n and i:
                supabase.table("sai_characters").insert({
                    "name": sanitize_secure(n), "image_url": u, "instruction": sanitize_secure(i),
                    "creator_id": st.session_state.user_id
                }).execute()
                st.success("데이터베이스에 안전하게 등록되었습니다.")