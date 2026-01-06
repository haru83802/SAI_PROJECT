import streamlit as st
from supabase import create_client, Client
from google import genai
import uuid

# --- [0. 시스템 초기화] ---
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# --- [1. 연결 설정] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"연결 오류: {e}")
    st.stop()

# --- [2. 사이드바 및 모델 선택] ---
with st.sidebar:
    st.title("🤖 SAI AI ENGINE")
    
    # [수정] 모델별 특징에 따른 SAI 엔진 타입 선택
    sai_type = st.radio(
        "SAI 모드 설정",
        ["BASIC", "PRO", "STORY", "ROLLPLAYING"],
        help="각 모델은 기억력과 지시 이행력이 다릅니다."
    )
    
    selected_model = st.selectbox(
        "기반 모델(LLM)", 
        ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
    )
    target_engine = selected_model.replace("models/", "")
    
    st.divider()
    st.subheader("📝 대화 목록")
    for sid, data in st.session_state.chat_sessions.items():
        if st.button(f"💬 {data['char_name']}", key=sid, use_container_width=True):
            st.session_state.current_session_id = sid
            st.rerun()

    if st.button("➕ 새 대화 시작", use_container_width=True):
        st.session_state.current_session_id = None
        st.rerun()

# --- [3. 메인 콘텐츠] ---
tabs = st.tabs(["💬 SAI 챗봇", "🔥 트렌드", "🛠️ 제작소"])

# [채팅창 탭]
with tabs[0]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("👈 사이드바에서 대화방을 선택하거나 새 대화를 시작하세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        
        # --- [추가] 실시간 캐릭터 설정 수정 (선택 지도) ---
        with st.expander(f"⚙️ {chat['char_name']} 설정 수정 (실시간)", expanded=False):
            new_inst = st.text_area("캐릭터 지침 수정", value=chat['instruction'], height=150)
            if st.button("설정 반영하기"):
                st.session_state.chat_sessions[sid]['instruction'] = new_inst
                st.success("지침이 실시간으로 업데이트되었습니다!")
                st.rerun()
        
        st.divider()

        # 대화 기록 표시
        if "messages" not in chat:
            chat["messages"] = []
        
        for m in chat["messages"]:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        if prompt := st.chat_input("메시지를 입력하세요..."):
            chat["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            # --- [수정] SAI 모델별 파라미터 분기 로직 ---
            config_dict = {
                "BASIC": {"temp": 0.7, "top_p": 0.9},
                "PRO": {"temp": 0.5, "top_p": 0.8},       # 낮은 온도 (정확성/참고율 업)
                "STORY": {"temp": 1.0, "top_p": 0.95},    # 높은 온도 (창의성/스토리 업)
                "ROLLPLAYING": {"temp": 0.9, "top_p": 1.0} # 자유로운 반응
            }
            current_config = config_dict.get(sai_type)

            try:
                # 대화 컨텍스트 구성 (기억력 반영)
                # Story 모델은 더 긴 기억력을 갖도록 history를 조절할 수 있습니다.
                context_history = chat["messages"][-20:] if sai_type != "STORY" else chat["messages"][-50:]

                response = client.models.generate_content(
                    model=target_engine,
                    contents=prompt,
                    config={
                        'system_instruction': chat['instruction'],
                        'temperature': current_config['temp'],
                        'top_p': current_config['top_p']
                    }
                )
                ai_text = response.text
                
                chat["messages"].append({"role": "assistant", "content": ai_text})
                with st.chat_message("assistant"):
                    st.write(ai_text)
                    
            except Exception as e:
                st.error(f"❌ 엔진 오류: {e}")

# [트렌드/제작소 탭은 기존 코드와 동일하게 유지]
with tabs[1]:
    st.header("🔥 인기 캐릭터")
    # ... (기존 코드 유지)
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        for char in chars:
            if st.button(f"선택: {char['name']}", key=f"sel_{char['id']}"):
                new_id = str(uuid.uuid4())
                st.session_state.chat_sessions[new_id] = {
                    "char_name": char['name'], 
                    "instruction": char['instruction'],
                    "messages": [] # 메시지 로그 초기화 추가
                }
                st.session_state.current_session_id = new_id
                st.rerun()
    except:
        st.write("캐릭터를 불러올 수 없습니다.")

with tabs[2]:
    st.header("🛠️ 캐릭터 제작소")
    with st.form("make"):
        name = st.text_input("이름")
        inst = st.text_area("AI 지침 (성격 등)")
        if st.form_submit_button("생성"):
            supabase.table("sai_characters").insert({"name": name, "instruction": inst}).execute()
            st.success("생성 완료!")
