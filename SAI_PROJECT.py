import streamlit as st
from supabase import create_client
import google.generativeai as genai
import uuid
import hashlib

# --- [0. 보안 및 초기화] ---
st.set_page_config(page_title="SAI - Zeta Experience", layout="wide", page_icon="🤖")

@st.cache_resource
def init_core():
    # 비영리 목적: API 키 및 DB 연결 보안 처리
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return sb
    except Exception as e:
        st.error(f"초기 설정 에러: Secrets 설정을 확인하세요. ({e})")
        st.stop()

supabase = init_core()

# 세션 관리 (Zeta처럼 대화가 끊기지 않게 유지)
if "user_id" not in st.session_state:
    st.session_state.user_id = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:10]
if "active_char" not in st.session_state:
    st.session_state.active_char = None
if "chat_session" not in st.session_state:
    st.session_state.chat_session = str(uuid.uuid4())

# --- [1. 스타일리시 헤더 (제타 감성)] ---
def draw_header():
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 25px; border-radius: 15px; border-left: 5px solid #00ffcc; margin-bottom: 25px;">
            <h1 style="color: #00ffcc; margin:0;">🤖 SAI : Zeta Master Edition</h1>
            <p style="color: #ffffff; margin: 5px 0;">비영리 목적의 초몰입형 AI 캐릭터 플랫폼</p>
            <span style="background: #00ffcc; color: #000; padding: 2px 8px; border-radius: 5px; font-size: 12px; font-weight: bold;">NON-PROFIT</span>
            <span style="color: #888; font-size: 12px; margin-left: 10px;">User: {st.session_state.user_id}</span>
        </div>
    """, unsafe_allow_html=True)

draw_header()

# --- [2. 메인 탭 (모든 요청 기능 통합)] ---
tabs = st.tabs(["🔍 캐릭터 탐색", "💬 채팅룸", "🛠️ 캐릭터 제작소", "📜 시스템 로그"])

# [탭 1: 실시간 검색 및 캐릭터 리스트]
with tabs[0]:
    # 검색 기능 추가
    search_col1, search_col2 = st.columns([4, 1])
    with search_col1:
        search_q = st.text_input("🔍 이름이나 키워드로 캐릭터를 찾아보세요", placeholder="예: 츤데레, 학생회장, 판타지...")
    
    # DB에서 캐릭터 로드 (에러 디버깅 완료)
    try:
        query = supabase.table("sai_characters").select("*").order("views", desc=True)
        if search_q:
            # 실시간 필터링 쿼리
            res = query.or_(f"name.ilike.%{search_q}%,description.ilike.%{search_q}%").execute()
        else:
            res = query.limit(12).execute()
        
        chars = res.data if res.data else []
        
        if not chars:
            st.info("검색 결과가 없습니다. 새로운 영혼을 직접 창조해 보세요!")
        else:
            # 3열 그리드 배치
            rows = [chars[i:i + 3] for i in range(0, len(chars), 3)]
            for row in rows:
                cols = st.columns(3)
                for i, char in enumerate(row):
                    with cols[i]:
                        with st.container(border=True):
                            if char.get('image_url'):
                                st.image(char['image_url'], use_container_width=True)
                            st.subheader(char['name'])
                            st.caption(char.get('description', '설명이 없는 캐릭터입니다.'))
                            st.write(f"👁️ {char.get('views', 0)}  ❤️ {char.get('likes', 0)}")
                            
                            if st.button("대화하기", key=f"chat_{char['id']}", use_container_width=True):
                                # 조회수 업데이트
                                supabase.table("sai_characters").update({"views": char.get('views', 0) + 1}).eq("id", char['id']).execute()
                                st.session_state.active_char = char
                                st.rerun()
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")

# [탭 2: 채팅룸 (제타 페르소나 몰입 엔진)]
with tabs[1]:
    if not st.session_state.active_char:
        st.warning("먼저 '캐릭터 탐색' 탭에서 대화할 캐릭터를 골라주세요.")
    else:
        char = st.session_state.active_char
        st.subheader(f"✨ {char['name']}와(과) 대화 중")
        
        # 이전 대화 기록 복구
        chat_res = supabase.table("chat_history").select("*").eq("session_id", st.session_state.chat_session).order("created_at").execute()
        history = chat_res.data if chat_res.data else []
        
        for m in history:
            with st.chat_message(m['role']):
                st.write(m['content'])

        # 사용자 입력 및 AI 응답 (Zeta 스타일 지침 적용)
        if prompt := st.chat_input(f"{char['name']}에게 메시지 보내기..."):
            with st.chat_message("user"):
                st.write(prompt)
            
            # 제타 스타일 프롬프트 엔지니어링
            system_instruction = f"""
            당신은 '{char['name']}'입니다. 다음 지침을 완벽히 따르세요:
            1. 페르소나: {char['instruction']}
            2. Zeta 스타일: 대화 중간에 반드시 ()를 사용하여 현재의 행동, 표정, 감정 상태를 묘사하십시오.
            3. 말투: 설정된 성격에 맞는 어투를 끝까지 유지하십시오.
            4. 상황: {char.get('scenario', '사용자와 대화 중')}
            """
            
            try:
                model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
                # 컨텍스트 연결을 위해 이전 대화 요약/전달 가능 (여기서는 간략화)
                response = model.generate_content(prompt).text
                
                with st.chat_message("assistant"):
                    st.write(response)
                
                # DB 저장 (에러 방지를 위해 리스트 형태로 삽입)
                supabase.table("chat_history").insert([
                    {"user_id": st.session_state.user_id, "session_id": st.session_state.chat_session, "role": "user", "content": prompt, "char_name": char['name']},
                    {"user_id": st.session_state.user_id, "session_id": st.session_state.chat_session, "role": "assistant", "content": response, "char_name": char['name']}
                ]).execute()
            except Exception as e:
                st.error(f"AI 응답 에러: {e}")

# [탭 3: 캐릭터 제작소]
with tabs[2]:
    st.header("🛠️ 신규 캐릭터 창작")
    st.write("제타 사이트의 분석 결과를 바탕으로 최적화된 설정 항목입니다.")
    
    with st.form("creator_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("캐릭터 이름 *", placeholder="예: 차가운 도련님")
            new_desc = st.text_input("한 줄 소개", placeholder="캐릭터를 한 문장으로 표현하세요.")
        with col2:
            new_img = st.text_input("이미지 URL", placeholder="https://... (비워두면 기본 이미지)")
            
        new_inst = st.text_area("상세 페르소나 & 행동 지침 *", placeholder="어떤 말투를 쓰는지, 어떤 상황에서 어떻게 반응하는지 적어주세요.", height=150)
        new_scen = st.text_area("시작 시나리오", placeholder="사용자와 처음 만났을 때 AI가 처한 상황을 적어주세요.", height=100)
        
        submit = st.form_submit_button("캐릭터 생성하기")
        if submit:
            if new_name and new_inst:
                try:
                    supabase.table("sai_characters").insert({
                        "name": new_name,
                        "description": new_desc,
                        "instruction": new_inst,
                        "scenario": new_scen,
                        "image_url": new_img,
                        "creator_id": st.session_state.user_id
                    }).execute()
                    st.success(f"✅ '{new_name}' 캐릭터가 성공적으로 생성되었습니다! 탐색 탭에서 확인하세요.")
                except Exception as e:
                    st.error(f"생성 실패: {e}")
            else:
                st.warning("이름과 행동 지침은 필수 항목입니다.")

# [탭 4: 시스템 로그 & 고지]
with tabs[3]:
    st.subheader("📝 Developer Notes")
    st.info("이 프로그램은 교육 및 비영리 목적으로 제작되었습니다.")
    st.write(f"- **Current User Hash:** {st.session_state.user_id}")
    st.write(f"- **Current Session ID:** {st.session_state.chat_session}")
    st.write("- **Applied Fixes:** Postgrest APIError, Search Null filtering, Zeta Persona Injection.")
    
    if st.button("세션 초기화 (대화 내역 삭제 아님)"):
        st.session_state.active_char = None
        st.session_state.chat_session = str(uuid.uuid4())
        st.rerun()