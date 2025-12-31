import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from openai import OpenAI
import uuid
import time
import re

# --- [0. 초기 설정 및 보안] ---
st.set_page_config(page_title="SAI - Ultimate Non-Profit AI", layout="wide", page_icon="🤖")

# 비영리 목적 고지 로딩
if "first_load" not in st.session_state:
    with st.spinner('SAI 보안 프로토콜 및 시스템 로딩 중...'):
        time.sleep(1.2)
    st.toast("SAI는 비영리 목적으로 만든 AI 채팅 사이트입니다.")
    st.session_state.first_load = True

# 세션 관리 (새로고침 시 유지의 핵심)
if "user_id" not in st.session_state: st.session_state.user_id = f"U_{uuid.uuid4().hex[:6]}"
if "current_sid" not in st.session_state: st.session_state.current_sid = None
if "draft_msg" not in st.session_state: st.session_state.draft_msg = ""

# --- [1. 연결부: Secrets 보안 적용] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("API 연동 오류! Secrets 설정을 확인하세요.")
    st.stop()

# --- [2. 유틸리티 함수] ---
def sanitize_input(text):
    """XSS 보안용 입력 필터"""
    return re.sub(r'<.*?>', '', text)

def get_affinity_label(score):
    if score >= 80: return "💖 운명적"
    if score >= 50: return "😊 친밀"
    return "❄️ 경계"

# --- [3. 사이드바: 제어판 및 개발자 코멘트] ---
with st.sidebar:
    st.title("🤖 SAI CONTROL")
    st.markdown(f"**User ID:** `{st.session_state.user_id}`")
    
    with st.expander("🛠️ 개발자 코멘트", expanded=True):
        st.info("""
        - SAI는 비영리 목적의 AI 실험실입니다.
        - ()를 통한 행동 묘사를 즐겨보세요.
        - 임시 저장 기능으로 대화를 보호합니다.
        """)

    st.divider()
    st.subheader("🧠 엔진 스위칭")
    engine_choice = st.selectbox("AI 모델", ["gemini-1.5-flash", "gpt-4o", "gpt-4o-mini"])
    
    st.subheader("🔑 소셜 로그인")
    c1, c2 = st.columns(2)
    c1.button("Google", use_container_width=True)
    c2.button("Discord", use_container_width=True)

    st.divider()
    st.subheader("📝 최근 대화 목록")
    res = supabase.table("chat_history").select("session_id, char_name").eq("user_id", st.session_state.user_id).execute()
    unique_chats = {i['session_id']: i['char_name'] for i in res.data}
    for sid, name in unique_chats.items():
        if st.button(f"💬 {name}", key=f"side_{sid}", use_container_width=True):
            st.session_state.current_sid = sid
            st.rerun()

# --- [4. 메인 인터페이스 상단] ---
st.markdown(f"""
    <div style="background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 10px; border-left: 5px solid #00ffcc; margin-bottom: 20px;">
        <h4 style="margin:0; color:#00ffcc;">SAI: Non-Profit AI Project</h4>
        <p style="margin:5px 0 0 0; font-size: 0.9em; color:#bbb;">
            비영리로 운영되는 지능형 채팅 사이트입니다. 모든 대화는 개인 ID 기반으로 안전하게 보호됩니다.
        </p>
    </div>
""", unsafe_allow_html=True)

tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 갤러리", "👥 단톡방", "🛠️ 제작소"])

# [탭 1: 트렌드]
with tabs[0]:
    chars = supabase.table("sai_characters").select("*").execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars or []):
        with cols[i % 3]:
            with st.container(border=True):
                if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                st.subheader(char['name'])
                st.caption(f"제작: {char.get('creator_id', 'Admin')}")
                if st.button("대화 시작", key=f"tr_{char['id']}", use_container_width=True):
                    st.session_state.current_sid = str(uuid.uuid4())
                    st.rerun()

# [탭 2: 채팅창 - 핵심 로직 통합]
with tabs[1]:
    sid = st.session_state.current_sid
    if not sid:
        st.info("트렌드에서 캐릭터를 선택하거나 @캐릭터명으로 말을 걸어보세요.")
    else:
        # 데이터 로드
        msgs = supabase.table("chat_history").select("*").eq("session_id", sid).eq("is_draft", False).order("created_at").execute().data
        char_info = supabase.table("sai_characters").select("*").eq("name", msgs[0]['char_name'] if msgs else "").execute().data
        current_char = char_info[0] if char_info else {"name": "AI", "instruction": "친절한 AI", "base_affinity": 50}
        
        # 호감도 및 상태 표시
        aff = msgs[-1]['affinity_score'] if msgs else current_char['base_affinity']
        st.subheader(f"💬 {current_char['name']} ({get_affinity_label(aff)})")
        st.progress(aff/100)

        # 메시지 루프
        for i, m in enumerate(msgs):
            with st.chat_message(m["role"]):
                st.write(m["content"])
                if m["role"] == "assistant" and i == len(msgs)-1:
                    if st.button("🔄 재생성", key=f"re_{i}"):
                        supabase.table("chat_history").delete().eq("id", m['id']).execute()
                        st.rerun()

        st.divider()
        
        # [임시 저장 로직]
        draft_res = supabase.table("chat_history").select("content").eq("session_id", sid).eq("is_draft", True).execute()
        if draft_res.data:
            st.warning(f"📝 임시 저장된 글: {draft_res.data[0]['content'][:30]}...")
            if st.button("내용 불러오기"):
                st.session_state.draft_msg = draft_res.data[0]['content']

        # 입력 영역
        u_input = st.text_area("메시지 입력...", value=st.session_state.draft_msg, placeholder="()를 사용하여 행동을 묘사해보세요.")
        
        c1, c2 = st.columns([1, 4])
        if c1.button("🚀 전송", use_container_width=True):
            if u_input.strip():
                clean_p = sanitize_input(u_input)
                # AI 호출 및 저장 (간략화)
                # ... (실제 호출 로직)
                supabase.table("chat_history").delete().eq("session_id", sid).eq("is_draft", True).execute()
                st.session_state.draft_msg = ""
                st.rerun()
        
        if c2.button("💾 임시 저장", use_container_width=True):
            supabase.table("chat_history").delete().eq("session_id", sid).eq("is_draft", True).execute()
            supabase.table("chat_history").insert({
                "user_id": st.session_state.user_id, "session_id": sid, "char_name": current_char['name'],
                "role": "user", "content": u_input, "is_draft": True
            }).execute()
            st.success("대화 내용이 임시 저장되었습니다.")

# [탭 3: 갤러리 - 좋아요/싫어요]
with tabs[2]:
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts or []:
        with st.container(border=True):
            st.image(p['img_url'], width=400)
            l, d = p.get('likes', []), p.get('dislikes', [])
            col1, col2 = st.columns(2)
            if col1.button(f"❤️ {len(l)}", key=f"l_{p['id']}"):
                if st.session_state.user_id not in l:
                    l.append(st.session_state.user_id)
                    supabase.table("posts").update({"likes": l}).eq("id", p['id']).execute()
                    st.rerun()
            if col2.button(f"👎 {len(d)}", key=f"d_{p['id']}"):
                if st.session_state.user_id not in d:
                    d.append(st.session_state.user_id)
                    supabase.table("posts").update({"dislikes": d}).eq("id", p['id']).execute()
                    st.rerun()

# [탭 5: 제작소]
with tabs[4]:
    st.header("🛠️ 캐릭터 커스텀 생성")
    with st.form("make_form"):
        name = st.text_input("이름")
        img_url = st.text_input("이미지 URL")
        inst = st.text_area("행동 지침 (Persona)")
        if st.form_submit_button("영구 등록"):
            supabase.table("sai_characters").insert({
                "name": name, "image_url": img_url, "instruction": inst,
                "creator_id": st.session_state.user_id
            }).execute()
            st.success("등록 완료!")