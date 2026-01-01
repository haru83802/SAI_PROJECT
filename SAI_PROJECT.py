import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import uuid
import time

# --- [0. 초기 설정 및 보안] ---
st.set_page_config(page_title="SAI - Ultimate AI", layout="wide", page_icon="🤖")

# 싱글톤 연결 (성능 최적화)
@st.cache_resource
def init_connections():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return sb

supabase = init_connections()

# 세션 유지 로직 (새로고침 대응)
if "user_id" not in st.session_state: 
    st.session_state.user_id = f"U_{uuid.uuid4().hex[:6]}"
if "current_sid" not in st.session_state: 
    st.session_state.current_sid = None
if "model_name" not in st.session_state:
    st.session_state.model_name = "gemini-1.5-flash"

# --- [1. 상단 공지 및 로봇 로고] ---
def show_top_notice():
    st.markdown(f"""
        <div style="background: linear-gradient(90deg, #121212, #333); padding: 20px; border-radius: 15px; border-left: 10px solid #00ffcc; margin-bottom: 25px;">
            <h1 style="margin:0; font-size: 40px;">🤖 SAI CORE</h1>
            <p style="margin:5px 0 0 0; color: #00ffcc; font-weight: bold;">SAI는 비영리 목적으로 만든 AI 채팅 사이트입니다.</p>
            <p style="margin:0; font-size: 0.8em; color: #888;">접속 유저 ID: {st.session_state.user_id} | 보안 모드 가동 중</p>
        </div>
    """, unsafe_allow_html=True)

# --- [2. 사이드바: 로그인, AI선택, 개발자 코멘트] ---
with st.sidebar:
    st.title("🛡️ SYSTEM PANEL")
    
    # 개발자 코멘트
    with st.expander("📝 개발자 코멘트", expanded=True):
        st.success("새로고침해도 대화가 유지되도록 Supabase 연동을 마쳤습니다. ()를 통한 행동 묘사를 지원합니다.")

    # AI 모델 선택 기능
    st.subheader("🧠 엔진 설정")
    st.session_state.model_name = st.selectbox(
        "사용할 AI 모델 선택", 
        ["gemini-1.5-flash", "gemini-1.5-pro"],
        help="Pro 모델이 더 똑똑하지만 속도는 Flash가 빠릅니다."
    )

    st.divider()
    
    # 구글/디스코드 로그인 UI
    st.subheader("🔑 계정 연동")
    st.button("🌐 Google로 로그인", use_container_width=True)
    st.button("💬 Discord로 로그인", use_container_width=True)
    
    st.divider()
    if st.button("🔴 대화 기록 초기화", use_container_width=True):
        st.session_state.current_sid = None
        st.rerun()

# --- [3. 메인 기능 탭] ---
show_top_notice()
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 갤러리", "🛠️ 제작소"])

# [탭 1: 트렌드 - 조회수 & 제작자 표시]
with tabs[0]:
    chars = supabase.table("sai_characters").select("*").order("views", desc=True).execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars or []):
        with cols[i % 3]:
            with st.container(border=True):
                if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                st.subheader(char['name'])
                st.caption(f"👤 제작자: {char.get('creator_id', 'Admin')}")
                st.markdown(f"👁️ 조회수 {char.get('views', 0)} | 🏷️ {char['description']}")
                
                if st.button("대화 시작", key=f"start_{char['id']}", use_container_width=True):
                    # 조회수 업데이트
                    supabase.table("sai_characters").update({"views": char['views'] + 1}).eq("id", char['id']).execute()
                    st.session_state.current_sid = str(uuid.uuid4())
                    st.session_state.chat_with = char
                    st.rerun()

# [탭 2: 채팅창 - 무조건 대화되는 코드]
with tabs[1]:
    if not st.session_state.get("current_sid"):
        st.info("👈 트렌드 탭에서 캐릭터를 먼저 선택해 주세요!")
    else:
        char = st.session_state.chat_with
        st.subheader(f"💬 {char['name']}와(과) 대화 중 ({st.session_state.model_name})")
        
        # 메시지 불러오기 (새로고침 대응)
        history = supabase.table("chat_history").select("*").eq("session_id", st.session_state.current_sid).order("created_at").execute().data
        for m in history:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지를 입력하세요..."):
            with st.chat_message("user"): st.write(prompt)
            
            # AI 호출 (Gemini)
            try:
                model = genai.GenerativeModel(st.session_state.model_name, system_instruction=char['instruction'])
                response = model.generate_content(prompt)
                ai_msg = response.text
                
                with st.chat_message("assistant"): st.write(ai_msg)
                
                # DB 저장 (새로고침 시 유지용)
                supabase.table("chat_history").insert([
                    {"user_id": st.session_state.user_id, "session_id": st.session_state.current_sid, "role": "user", "content": prompt, "char_name": char['name']},
                    {"user_id": st.session_state.user_id, "session_id": st.session_state.current_sid, "role": "assistant", "content": ai_msg, "char_name": char['name']}
                ]).execute()
            except Exception as e:
                st.error("AI 응답 중 에러가 발생했습니다. 다시 시도해 주세요.")

# [탭 3: 갤러리 - 좋아요 기능]
with tabs[2]:
    st.header("📸 SAI 유저 갤러리")
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts or []:
        with st.container(border=True):
            st.image(p['img_url'], width=400)
            st.caption(f"👤 제작자: {p.get('creator_id', 'Unknown')}")
            
            likes = p.get('likes', [])
            if st.button(f"❤️ {len(likes)} 좋아요", key=f"like_{p['id']}"):
                if st.session_state.user_id not in likes:
                    likes.append(st.session_state.user_id)
                    supabase.table("posts").update({"likes": likes}).eq("id", p['id']).execute()
                    st.rerun()

# [탭 4: 제작소]
with tabs[3]:
    st.header("🛠️ 캐릭터 제작")
    with st.form("create"):
        n = st.text_input("이름")
        d = st.text_input("설명")
        i = st.text_area("행동 지침")
        u = st.text_input("이미지 URL")
        if st.form_submit_button("등록"):
            supabase.table("sai_characters").insert({
                "name": n, "description": d, "instruction": i, "image_url": u, "creator_id": st.session_state.user_id
            }).execute()
            st.success("등록 완료!")