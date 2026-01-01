import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from security import sai_guard
import uuid

# --- [0. 초기화] ---
if "user" not in st.session_state: st.session_state.user = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- [1. 설정 및 연결] ---
st.set_page_config(page_title="SAI - 모델 선택 기능", layout="wide", page_icon="🤖")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("Secrets 설정 오류!")
    st.stop()

# --- [2. 사이드바: 모델 버전 및 대화 목록] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    
    # --- [핵심: AI 버전 선택] ---
    st.subheader("⚙️ AI 모델 설정")
    selected_model = st.selectbox(
        "사용할 AI 버전을 선택하세요",
        ["gemini-1.5-flash", "gemini-1.5-pro"],
        index=0,
        help="Flash는 빠르고 가볍고, Pro는 더 똑똑하지만 느릴 수 있습니다."
    )
    st.write(f"현재 모드: **{selected_model}**")
    st.divider()

    st.subheader("📝 내 대화 목록")
    u_id = st.session_state.user.id if st.session_state.user else f"Guest_{sai_guard.get_remote_ip()}"
    
    # 대화 목록 로드 (서버 연동)
    if not st.session_state.chat_sessions:
        try:
            res = supabase.table("chat_history").select("session_id, char_name, instruction").eq("user_id", u_id).execute()
            for item in res.data:
                sid = str(item['session_id'])
                if sid not in st.session_state.chat_sessions:
                    st.session_state.chat_sessions[sid] = {"char_name": item['char_name'], "instruction": item['instruction'], "messages": []}
        except: pass

    for s_id, s_data in st.session_state.chat_sessions.items():
        if st.button(f"💬 {s_data['char_name']}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()

# --- [4. 메인 콘텐츠] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 캐릭터 선택]
with tabs[0]:
    st.subheader("캐릭터 선택")
    chars = supabase.table("sai_characters").select("*").execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars):
        with cols[i % 3]:
            if char.get('image_url'): st.image(char['image_url'])
            st.info(f"**{char['name']}**")
            if st.button("대화 시작", key=f"ch_{char['id']}"):
                new_id = str(uuid.uuid4())
                st.session_state.chat_sessions[new_id] = {
                    "char_name": char['name'], "instruction": char['instruction'], "messages": []
                }
                st.session_state.current_session_id = new_id
                st.rerun()

# [탭 2: 채팅창 - 선택된 모델 버전 적용]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.warning("캐릭터를 먼저 선택해 주세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.caption(f"현재 엔진: {selected_model}") # 어떤 모델 쓰고 있는지 표시
        
        # 메시지 불러오기 로직 (중략 - 이전과 동일)
        if not chat["messages"]:
            res = supabase.table("chat_history").select("*").eq("session_id", str(sid)).order("created_at").execute()
            chat["messages"] = [{"role": r["role"], "content": r["content"]} for r in res.data]

        for m in chat["messages"]:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지 입력..."):
            chat["messages"].append({"role": "user", "content": prompt})
            
            try:
                # 1. 유저 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "user", "content": prompt, "instruction": chat['instruction']
                }).execute()
                
                # 2. 선택된 버전(selected_model)으로 AI 호출
                model = genai.GenerativeModel(
                    model_name=f"models/{selected_model}", 
                    system_instruction=chat['instruction']
                )
                response = model.generate_content(prompt)
                ai_text = response.text
                
                # 3. AI 응답 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "assistant", "content": ai_text, "instruction": chat['instruction']
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"모델({selected_model}) 호출 실패: {e}")