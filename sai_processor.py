import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from openai import OpenAI
import uuid
import time

# --- [0. 로딩 메시지 및 초기 설정] ---
st.set_page_config(page_title="SAI - Non-Profit AI Project", layout="wide")

# 사이트 로딩 시 환영 메시지 (Toast 및 상단 고정)
if "first_load" not in st.session_state:
    with st.spinner('SAI 시스템을 불러오는 중...'):
        time.sleep(1.5)
        st.success("SAI는 비영리 목적으로 만든 AI채팅 사이트입니다.")
        st.session_state.first_load = True

# 세션 상태 관리
if "user_id" not in st.session_state: st.session_state.user_id = f"U_{uuid.uuid4().hex[:6]}"
if "current_sid" not in st.session_state: st.session_state.current_sid = None

# --- [1. 연결부] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.error("API 연동 실패. 관리자 설정을 확인하세요.")
    st.stop()

# --- [2. 상단 헤더 및 공지] ---
st.markdown(f"""
    <div style="background: rgba(0,0,0,0.1); padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin-bottom: 20px;">
        <h4 style="margin:0;">📢 SAI 프로젝트 안내</h4>
        <p style="margin:5px 0 0 0; font-size: 0.9em;">
            <b>SAI는 비영리 목적으로 만든 AI채팅 사이트입니다.</b> 유저 ID: <code>{st.session_state.user_id}</code><br>
            @캐릭터명 명령어로 대화 상대를 즉시 호출하거나 단톡방을 개설할 수 있습니다.
        </p>
    </div>
""", unsafe_allow_html=True)

# --- [3. 사이드바 - 개발자 콘솔 및 설정] ---
with st.sidebar:
    st.title("🛠️ SAI CONTROL")
    with st.expander("📝 개발자 코멘트", expanded=True):
        st.info("비영리 프로젝트로서 대화 품질과 기억력 향상에 집중했습니다. ()를 통한 행동 묘사를 지원합니다.")
    
    st.divider()
    model_choice = st.selectbox("엔진 선택", ["Gemini 1.5 Flash", "GPT-4o-mini", "GPT-4o"])
    m_map = {"Gemini 1.5 Flash": "gemini-1.5-flash", "GPT-4o-mini": "gpt-4o-mini", "GPT-4o": "gpt-4o"}
    sel_model = m_map[model_choice]

    st.subheader("🔑 계정")
    c1, c2 = st.columns(2)
    c1.button("Google", use_container_width=True)
    c2.button("Discord", use_container_width=True)

# --- [4. 메인 탭 구성] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅/단톡", "📸 갤러리", "👥 단톡방 개설", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드 & 캐릭터 이미지]
with tabs[0]:
    chars = supabase.table("sai_characters").select("*").execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars or []):
        with cols[i % 3]:
            with st.container(border=True):
                if char.get('image_url'):
                    st.image(char['image_url'], use_container_width=True)
                st.subheader(char['name'])
                st.write(char['description'])
                if st.button("대화 시작", key=f"start_{char['id']}", use_container_width=True):
                    st.session_state.current_sid = str(uuid.uuid4())
                    st.rerun()

# [탭 2: 채팅창 - 기억력/재생성/@기능/호감도 통합]
with tabs[1]:
    sid = st.session_state.current_sid
    if not sid:
        st.info("트렌드에서 캐릭터를 선택하거나 단톡방을 개설하세요.")
    else:
        history = supabase.table("chat_history").select("*").eq("session_id", sid).order("created_at").execute().data
        
        # UI: 상단 정보
        current_name = history[0]['char_name'] if history else "AI"
        st.subheader(f"💬 {current_name}와(과) 대화")
        
        for i, m in enumerate(history):
            with st.chat_message(m["role"]):
                st.write(m["content"])
                if m["role"] == "assistant" and i == len(history)-1:
                    if st.button("🔄 재생성", key=f"retry_{i}"):
                        supabase.table("chat_history").delete().eq("id", m['id']).execute()
                        st.rerun()

        if prompt := st.chat_input("메시지를 입력하세요..."):
            with st.chat_message("user"): st.write(prompt)
            # 대화 저장 및 AI 호출 로직 (생략된 기존 엔진 호출 부분 결합)
            st.toast("AI가 답변을 생각하고 있습니다...")
            # (여기에 이전 단계의 SAIEngine.generate_response 로직이 들어갑니다)

# [탭 4: 단톡방 개설]
with tabs[3]:
    st.header("👥 AI 단톡방 만들기")
    all_chars = [c['name'] for c in (chars or [])]
    with st.form("group_chat_form"):
        g_name = st.text_input("방 이름")
        members = st.multiselect("참여 캐릭터", all_chars)
        if st.form_submit_button("방 개설하기"):
            supabase.table("group_chats").insert({
                "group_name": g_name, "member_names": members, "creator_id": st.session_state.user_id
            }).execute()
            st.success("단톡방이 만들어졌습니다! 채팅 목록을 확인하세요.")

# [탭 5: 캐릭터 제작 - 이미지 및 호감도 설정]
with tabs[4]:
    st.header("🛠️ 캐릭터 커스텀 제작")
    with st.form("make_char"):
        name = st.text_input("이름")
        img = st.text_input("이미지 URL (직접 링크)")
        desc = st.text_input("설명")
        inst = st.text_area("AI 지침 (Persona)")
        aff = st.slider("초기 호감도", 0, 100, 50)
        if st.form_submit_button("영구 등록"):
            supabase.table("sai_characters").insert({
                "name": name, "image_url": img, "description": desc,
                "instruction": inst, "base_affinity": aff, "creator_id": st.session_state.user_id
            }).execute()
            st.success(f"{name} 캐릭터가 서버에 등록되었습니다.")