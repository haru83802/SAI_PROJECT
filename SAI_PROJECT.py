import streamlit as st
from supabase import create_client
import google.generativeai as genai
import uuid
import hashlib

# --- [0. 시스템 코어 및 에러 핸들링] ---
st.set_page_config(page_title="SAI - Zeta Master", layout="wide", page_icon="🤖")

@st.cache_resource
def init_system():
    try:
        # Supabase 연결
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        # Gemini 설정 (최신 라이브러리 표준)
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return sb
    except Exception as e:
        st.error(f"시스템 초기화 중 치명적 오류: {e}")
        st.stop()

supabase = init_system()

# 세션 유지 로직
if "user_id" not in st.session_state:
    st.session_state.user_id = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:12]
if "active_char" not in st.session_state:
    st.session_state.active_char = None
if "chat_session" not in st.session_state:
    st.session_state.chat_session = str(uuid.uuid4())

# --- [1. 제타 스타일 상단 공지] ---
st.markdown(f"""
    <div style="background: linear-gradient(90deg, #000428, #004e92); padding: 25px; border-radius: 15px; border-left: 8px solid #00ffcc; text-align: center; margin-bottom: 30px;">
        <h1 style="color: #00ffcc; margin:0; font-family: 'Apple SD Gothic Neo';">🤖 SAI CORE : ZETA MASTER</h1>
        <p style="color: #ffffff; margin: 10px 0; font-size: 1.1em;">비영리 목적의 초몰입형 AI 캐릭터 시뮬레이터</p>
        <div style="font-size: 0.8em; color: #aaa;">Authorized ID: {st.session_state.user_id} | Security Level: v1.5-Flash</div>
    </div>
""", unsafe_allow_html=True)

# --- [2. 메인 탭 시스템] ---
tabs = st.tabs(["🔍 캐릭터 검색/탐색", "💬 1:1 채팅룸", "🛠️ 캐릭터 창조", "📜 개발자 로그"])

# [탭 1: 검색 및 트렌드]
with tabs[0]:
    search_query = st.text_input("🔍 제타 스타일 캐릭터 검색", placeholder="성격, 태그, 이름으로 검색...")
    
    try:
        # DB에서 데이터 가져오기
        query = supabase.table("sai_characters").select("*").order("views", desc=True)
        if search_query:
            res = query.or_(f"name.ilike.%{search_query}%,description.ilike.%{search_query}%").execute()
        else:
            res = query.limit(15).execute()
        
        chars = res.data if res.data else []
        
        if not chars:
            st.info("찾으시는 영혼이 아직 없네요. 직접 만들어보세요!")
        else:
            cols = st.columns(3)
            for i, char in enumerate(chars):
                with cols[i % 3]:
                    with st.container(border=True):
                        if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                        st.subheader(char['name'])
                        st.caption(char.get('description', '신비주의 캐릭터'))
                        st.markdown(f"👁️ {char.get('views', 0):,}  ❤️ {char.get('likes', 0):,}")
                        
                        if st.button("운명적 대화 시작", key=f"btn_{char['id']}", use_container_width=True):
                            # 조회수 상승 및 세션 고정
                            supabase.table("sai_characters").update({"views": char.get('views', 0) + 1}).eq("id", char['id']).execute()
                            st.session_state.active_char = char
                            st.rerun()
    except Exception as e:
        st.error(f"DB 로드 실패: {e}")

# [탭 2: 채팅룸 - 404 에러 수정 버전]
with tabs[1]:
    if not st.session_state.active_char:
        st.info("왼쪽 '캐릭터 검색' 탭에서 대화할 대상을 선택해주세요.")
    else:
        char = st.session_state.active_char
        st.header(f"💬 {char['name']}와(과) 대화 중")
        
        # 채팅 내역 불러오기
        history_res = supabase.table("chat_history").select("*").eq("session_id", st.session_state.chat_session).order("created_at").execute()
        history_data = history_res.data if history_res.data else []
        
        for m in history_data:
            with st.chat_message(m['role']): st.write(m['content'])

        if prompt := st.chat_input(f"{char['name']}에게 메시지 전송..."):
            with st.chat_message("user"): st.write(prompt)
            
            # 404 에러 방지용 최적화 프롬프트
            # 'gemini-1.5-flash' 단독 명칭 사용 (v1beta 경로 제거)
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash", 
                    system_instruction=f"""
                    당신은 '{char['name']}'입니다. {char['instruction']}
                    Zeta 스타일 규칙: 
                    1. 반드시 괄호 ()를 사용하여 행동, 표정, 현재 상황을 묘사할 것.
                    2. 말투는 설정된 성격을 끝까지 고수할 것.
                    3. 비영리 프로젝트임을 인지하고 친절하되 몰입감 있게 대화할 것.
                    """
                )
                
                # 대화 생성
                response = model.generate_content(prompt)
                ai_text = response.text
                
                with st.chat_message("assistant"): st.write(ai_text)
                
                # DB 실시간 저장
                supabase.table("chat_history").insert([
                    {"user_id": st.session_state.user_id, "session_id": st.session_state.chat_session, "role": "user", "content": prompt, "char_name": char['name']},
                    {"user_id": st.session_state.user_id, "session_id": st.session_state.chat_session, "role": "assistant", "content": ai_text, "char_name": char['name']}
                ]).execute()
            except Exception as e:
                st.error(f"AI 응답 에러 (모델 설정 확인 필요): {e}")

# [탭 3: 캐릭터 창조]
with tabs[2]:
    st.header("🛠️ 제타 스타일 캐릭터 커스텀")
    with st.form("creator"):
        c1, c2 = st.columns(2)
        with c1:
            n = st.text_input("이름 (필수)")
            d = st.text_input("설명 (검색 키워드)")
        with c2:
            u = st.text_input("이미지 URL (HTTPS)")
        
        i = st.text_area("행동/성격 지침 (페르소나)", height=200, placeholder="예: 무뚝뚝하지만 다정한 학생회장. 괄호를 써서 감정을 표현함.")
        s = st.text_area("첫 만남 시나리오", placeholder="사용자가 말을 걸었을 때 캐릭터가 처해 있는 상황")
        
        if st.form_submit_button("영혼 등록하기"):
            if n and i:
                supabase.table("sai_characters").insert({
                    "name": n, "description": d, "instruction": i, "scenario": s, "image_url": u, "creator_id": st.session_state.user_id
                }).execute()
                st.success(f"🤖 {n} 캐릭터가 생성되었습니다! 탐색 탭에서 확인하세요.")

# [탭 4: 로그 및 리셋]
with tabs[3]:
    st.info("SAI 제타 마스터는 비영리 목적으로만 운영됩니다.")
    if st.button("현재 대화 세션 초기화"):
        st.session_state.chat_session = str(uuid.uuid4())
        st.session_state.active_char = None
        st.rerun()