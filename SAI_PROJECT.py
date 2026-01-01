import streamlit as st
from supabase import create_client
import google.generativeai as genai
import uuid
import hashlib
import re

# --- [0. 보안 및 초기화] ---
st.set_page_config(page_title="SAI - Zeta Experience", layout="wide", page_icon="🤖")

@st.cache_resource
def init_core():
    # 보안: Secrets가 없을 경우 안내
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return sb
    except Exception as e:
        st.error(f"설정 오류: Secrets를 확인하세요. ({e})")
        st.stop()

supabase = init_core()

# 세션 유지 및 사용자 보안 식별
if "user_id" not in st.session_state:
    st.session_state.user_id = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:12]
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

# --- [1. 제타 스타일 UI 렌더링] ---
def zeta_header():
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); padding: 30px; border-radius: 20px; border-bottom: 4px solid #00ffcc; text-align: center; margin-bottom: 30px;">
            <h1 style="margin:0; font-size: 60px;">🤖 SAI</h1>
            <h3 style="color: #00ffcc; margin: 10px 0;">Zeta-Inspired Non-Profit Platform</h3>
            <p style="color: #ccc;">비영리 목적으로 운영되는 초몰입형 AI 대화 서비스입니다.</p>
            <p style="font-size: 0.8em; color: #888;">User Hash: {st.session_state.user_id}</p>
        </div>
    """, unsafe_allow_html=True)

# --- [2. 핵심 기능: 대화 엔진 (디버깅 완료)] ---
def generate_ai_response(char_info, user_input, history_context):
    # Zeta의 핵심: 페르소나 + 시나리오 + 유저 입력 결합
    full_prompt = f"""
    당신은 다음의 캐릭터 페르소나를 완벽하게 연기하십시오:
    캐릭터 이름: {char_info['name']}
    성격/지침: {char_info['instruction']}
    현재 상황: {char_info.get('scenario', '사용자와 첫 대화를 시작함')}
    
    주의사항:
    1. 괄호 ()를 사용하여 행동, 감정, 주변 상황을 묘사하십시오. (예: (당신을 빤히 바라보며 입술을 깨문다))
    2. 캐릭터의 말투와 성격을 대화 끝까지 유지하십시오.
    3. 이전 대화 맥락을 기억하십시오.
    """
    
    try:
        model = genai.GenerativeModel("gemini-1.5-pro") # 더 깊은 몰입을 위해 Pro 권장
        # 대화 맥락 생성
        chat = model.start_chat(history=history_context)
        response = chat.send_message(user_input)
        return response.text
    except Exception as e:
        return f"(시스템 오류 발생: {e}. 잠시 후 다시 시도해주세요.)"

# --- [3. 메인 인터페이스] ---
zeta_header()
tabs = st.tabs(["✨ 트렌드 & 검색", "💬 채팅룸", "🛠️ 캐릭터 창작", "📜 개발자 노드"])

# [탭 1: 캐릭터 탐색 및 검색]
with tabs[0]:
    search_col1, search_col2 = st.columns([4, 1])
    search_q = search_col1.text_input("🔍 당신이 꿈꾸던 캐릭터를 찾아보세요", placeholder="이름, 키워드 검색...")
    
    # 데이터 로드 및 에러 방지 처리
    res = supabase.table("sai_characters").select("*").order("views", desc=True).execute()
    chars = res.data if res.data else []
    
    if search_q:
        chars = [c for c in chars if search_q.lower() in c['name'].lower() or search_q.lower() in c.get('description', '').lower()]

    rows = [chars[i:i + 3] for i in range(0, len(chars), 3)]
    for row in rows:
        cols = st.columns(3)
        for i, char in enumerate(row):
            with cols[i]:
                with st.container(border=True):
                    if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                    st.subheader(char['name'])
                    st.write(char.get('description', '설명이 없습니다.'))
                    st.markdown(f"👁️ {char.get('views', 0)} | ❤️ {char.get('likes', 0)}")
                    
                    if st.button("대화 시작", key=f"btn_{char['id']}", use_container_width=True):
                        # 조회수 증가 (APIError 방지를 위한 안전 업데이트)
                        try:
                            supabase.table("sai_characters").update({"views": char.get('views', 0) + 1}).eq("id", char['id']).execute()
                        except: pass
                        st.session_state.chat_session = str(uuid.uuid4())
                        st.session_state.active_char = char
                        st.rerun()

# [탭 2: 채팅룸 (Zeta 스타일 몰입)]
with tabs[1]:
    if not st.session_state.get("active_char"):
        st.info("트렌드 탭에서 캐릭터를 선택하여 운명적인 대화를 시작하세요.")
    else:
        current_char = st.session_state.active_char
        st.subheader(f"✨ {current_char['name']}와(과) 대화 중")
        
        # DB에서 대화 내역 복구 (새로고침 시 유지 핵심)
        db_history = supabase.table("chat_history").select("*").eq("session_id", st.session_state.chat_session).order("created_at").execute().data
        
        # UI 출력용
        for m in db_history:
            with st.chat_message(m['role']):
                st.write(m['content'])

        # 사용자 입력
        if prompt := st.chat_input(f"{current_char['name']}에게 할 말을 적어주세요..."):
            with st.chat_message("user"):
                st.write(prompt)
            
            # 컨텍스트 구축
            history_for_api = [{"role": "user" if m['role'] == "user" else "model", "parts": [m['content']]} for m in db_history]
            
            # AI 응답 생성
            with st.spinner(f"{current_char['name']}(이)가 생각 중..."):
                ai_response = generate_ai_response(current_char, prompt, history_for_api)
            
            with st.chat_message("assistant"):
                st.write(ai_response)
            
            # DB 저장 (트랜잭션 오류 방지를 위해 리스트로 전송)
            supabase.table("chat_history").insert([
                {"user_id": st.session_state.user_id, "session_id": st.session_state.chat_session, "role": "user", "content": prompt, "char_name": current_char['name']},
                {"user_id": st.session_state.user_id, "session_id": st.session_state.chat_session, "role": "assistant", "content": ai_response, "char_name": current_char['name']}
            ]).execute()

# [탭 3: 캐릭터 창작 (Zeta 스타일 페르소나)]
with tabs[2]:
    st.header("🛠️ 새로운 영혼 창조")
    with st.form("creator_form"):
        c_name = st.text_input("이름", placeholder="캐릭터의 이름을 정해주세요.")
        c_desc = st.text_input("한 줄 소개", placeholder="트렌드에 표시될 매력적인 문구")
        c_inst = st.text_area("페르소나 설정", placeholder="성격, 말투, 금기사항 등을 상세히 적어주세요.", height=200)
        c_scen = st.text_area("첫 만남 시나리오", placeholder="사용자가 처음 말을 걸었을 때 AI가 처한 상황을 묘사하세요.")
        c_img = st.text_input("이미지 URL", placeholder="https://...")
        
        if st.form_submit_button("영혼 불어넣기"):
            if c_name and c_inst:
                try:
                    supabase.table("sai_characters").insert({
                        "name": c_name, "instruction": c_inst, "scenario": c_scen,
                        "description": c_desc, "image_url": c_img, "creator_id": st.session_state.user_id
                    }).execute()
                    st.success("🤖 새로운 캐릭터가 탄생했습니다!")
                except Exception as e:
                    st.error(f"창조 실패: {e}")

# [탭 4: 개발자 노드 (비영리 고지 및 세션 제어)]
with tabs[3]:
    st.info("SAI는 비영리 목적으로 운영되는 실험적 AI 플랫폼입니다.")
    st.write("본 서비스는 어떠한 수익도 창출하지 않으며, 모든 AI 모델의 비용은 개발자가 부담하거나 무료 티어를 활용합니다.")
    if st.button("🔴 현재 대화 세션 종료"):
        st.session_state.chat_session = None
        st.session_state.active_char = None
        st.rerun()