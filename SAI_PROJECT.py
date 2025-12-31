import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from openai import OpenAI
import uuid

# --- [0. 초기 설정 및 세션 유지] ---
st.set_page_config(page_title="SAI - Gemini & GPT Hybrid", layout="wide", page_icon="🤖")

if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
# 기본 모델 설정
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gemini-1.5-flash"

# --- [1. API 연결 설정] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # OpenAI 클라이언트 초기화
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"연결 설정 오류: Secrets에 API 키들을 확인하세요. ({e})")
    st.stop()

# --- [2. 상단 공지사항] ---
st.markdown("""
    <div style="background-color:#1E1E1E; color:white; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #00D1FF;">
        <strong>📢 SAI 시스템 공지:</strong> 이제 <strong>ChatGPT(GPT-4o)</strong>와 <strong>Gemini 1.5</strong>를 자유롭게 선택하여 대화할 수 있습니다!
    </div>
""", unsafe_allow_html=True)

# --- [3. 사이드바 - 로그인 및 AI 선택] ---
with st.sidebar:
    st.title("🤖 SAI CONTROL")
    st.info("💡 **Dev Comment:** 모델을 변경하면 즉시 해당 AI의 뇌로 교체됩니다.")
    
    # 모델 선택 섹션 (GPT와 Gemini 통합)
    st.subheader("🧠 AI 모델 엔진 선택")
    model_option = st.selectbox(
        "사용할 AI를 선택하세요",
        [
            "Gemini 1.5 Flash (빠름)", 
            "Gemini 1.5 Pro (정교함)", 
            "GPT-4o mini (효율적)",
            "GPT-4o (강력함)"
        ]
    )
    
    # 선택된 값을 시스템용 모델 이름으로 변환
    model_mapping = {
        "Gemini 1.5 Flash (빠름)": "gemini-1.5-flash",
        "Gemini 1.5 Pro (정교함)": "gemini-1.5-pro",
        "GPT-4o mini (효율적)": "gpt-4o-mini",
        "GPT-4o (강력함)": "gpt-4o"
    }
    st.session_state.selected_model = model_mapping[model_option]

    # 소셜 로그인 버튼
    st.subheader("🔑 소셜 계정 연결")
    c1, c2 = st.columns(2)
    if c1.button("Google"): st.toast("구글 로그인 시뮬레이션 성공")
    if c2.button("Discord"): st.toast("디스코드 로그인 시뮬레이션 성공")

    # 대화 목록 로드 (새로고침 유지용)
    st.subheader("📝 저장된 대화")
    try:
        res = supabase.table("chat_history").select("session_id, char_name").eq("user_id", st.session_state.user_id).execute()
        unique_sessions = {item['session_id']: item['char_name'] for item in res.data}
        for sid, name in unique_sessions.items():
            if st.button(f"💬 {name}", key=f"list_{sid}", use_container_width=True):
                st.session_state.current_session_id = sid
                st.rerun()
    except:
        st.caption("저장된 대화가 없습니다.")

# --- [4. 메인 기능 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 갤러리", "🛠️ 캐릭터 생성"])

# [탭 1: 트렌드]
with tabs[0]:
    chars = supabase.table("sai_characters").select("*").execute().data
    if not chars:
        st.warning("SQL 초기화 코드를 실행하여 기본 캐릭터를 생성해주세요.")
    else:
        cols = st.columns(3)
        for i, char in enumerate(chars):
            with cols[i % 3]:
                with st.container(border=True):
                    st.subheader(char['name'])
                    st.caption(f"제작자: {char.get('creator_id', 'System')}")
                    if st.button("대화 시작", key=f"char_{char['id']}", use_container_width=True):
                        st.session_state.current_session_id = str(uuid.uuid4())
                        st.rerun()

# [탭 2: 채팅창 - GPT/Gemini 하이브리드 로직]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("사이드바에서 대화를 선택하거나 트렌드에서 캐릭터를 골라주세요.")
    else:
        # DB에서 현재 대화의 지침(Instruction) 찾기
        res_info = supabase.table("chat_history").select("char_name, instruction").eq("session_id", sid).limit(1).execute()
        
        # 만약 신규 대화라면 캐릭터 테이블에서 가져옴
        if not res_info.data:
            # 여기서는 편의상 첫 번째 캐릭터 정보를 기본값으로 사용하거나 캐릭터 선택 정보를 유지해야 함
            char_name, instruction = "AI", "친절한 AI입니다."
        else:
            char_name = res_info.data[0]['char_name']
            instruction = res_info.data[0]['instruction']

        st.subheader(f"💬 {char_name} ({st.session_state.selected_model})")

        # 대화 내용 불러오기
        res_msg = supabase.table("chat_history").select("*").eq("session_id", sid).order("created_at").execute()
        for m in res_msg.data:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지를 입력하세요..."):
            with st.chat_message("user"): st.write(prompt)
            
            # 1. 유저 메시지 저장
            supabase.table("chat_history").insert({
                "user_id": st.session_state.user_id, "session_id": sid, "char_name": char_name,
                "role": "user", "content": prompt, "instruction": instruction
            }).execute()

            # 2. 선택된 모델에 따른 AI 응답 생성
            ai_text = ""
            current_model = st.session_state.selected_model

            try:
                if "gemini" in current_model:
                    # Gemini 호출
                    model = genai.GenerativeModel(model_name=current_model, system_instruction=instruction)
                    response = model.generate_content(prompt)
                    ai_text = response.text
                else:
                    # ChatGPT 호출 (OpenAI)
                    response = openai_client.chat.completions.create(
                        model=current_model,
                        messages=[
                            {"role": "system", "content": instruction},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    ai_text = response.choices[0].message.content

                with st.chat_message("assistant"): st.write(ai_text)

                # 3. AI 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": st.session_state.user_id, "session_id": sid, "char_name": char_name,
                    "role": "assistant", "content": ai_text, "instruction": instruction
                }).execute()
            except Exception as e:
                st.error(f"AI 호출 중 오류 발생: {e}")

# [탭 3: 갤러리 & 좋아요 기능]
with tabs[2]:
    st.header("📸 AI 갤러리")
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts:
        with st.container(border=True):
            st.image(p['img_url'], width=500)
            st.write(f"📝 {p['description']}")
            st.caption(f"👤 제작자: {p['user_id']}")
            
            likes = p.get('likes', [])
            if st.button(f"❤️ {len(likes)} 좋아요", key=f"like_{p['id']}"):
                if st.session_state.user_id not in likes:
                    likes.append(st.session_state.user_id)
                    supabase.table("posts").update({"likes": likes}).eq("id", p['id']).execute()
                    st.rerun()

# [탭 4: 캐릭터 생성]
with tabs[3]:
    with st.form("create"):
        name = st.text_input("캐릭터 이름")
        inst = st.text_area("AI 지침 (페르소나)")
        if st.form_submit_button("서버 등록"):
            supabase.table("sai_characters").insert({
                "name": name, "instruction": inst, "creator_id": st.session_state.user_id
            }).execute()
            st.success("새로운 캐릭터가 등록되었습니다!")