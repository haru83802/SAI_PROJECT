import streamlit as st
from supabase import create_client, Client
from google import genai
from google.genai import types
import uuid

# --- [0. 시스템 초기화] ---
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# --- [1. 연결 설정] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"연결 오류: {e}")
    st.stop()

# --- [2. 함수: DB 데이터 로드/저장] ---
def load_sessions():
    """DB에서 모든 대화 목록을 가져옴"""
    return supabase.table("chat_sessions").select("*").order("created_at", desc=True).execute().data

def load_messages(sid):
    """특정 세션의 대화 기록을 DB에서 가져옴"""
    return supabase.table("chat_messages").select("*").eq("session_id", sid).order("created_at").execute().data

def save_message(sid, role, content):
    """메시지를 DB에 영구 저장"""
    supabase.table("chat_messages").insert({
        "session_id": sid,
        "role": role,
        "content": content
    }).execute()

# --- [3. 사이드바] ---
with st.sidebar:
    st.title("🤖 SAI AI ENGINE")
    
    sai_mode = st.radio("SAI 모드", ["BASIC", "PRO", "STORY", "ROLLPLAYING"])
    selected_model = st.selectbox("엔진", ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro"])
    
    st.divider()
    st.subheader("📝 내 대화 기록")
    sessions = load_sessions()
    for s in sessions:
        if st.button(f"💬 {s['char_name']}", key=s['id'], use_container_width=True):
            st.session_state.current_session_id = s['id']
            st.rerun()

# --- [4. 메인 콘텐츠] ---
tabs = st.tabs(["💬 SAI 챗봇", "🔥 트렌드", "🛠️ 제작소"])

with tabs[0]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("👈 사이드바에서 대화를 선택하거나 트렌드에서 캐릭터를 고르세요.")
    else:
        # 현재 세션 정보 가져오기
        current_session = supabase.table("chat_sessions").select("*").eq("id", sid).single().execute().data
        
        # [실시간 지침 수정]
        with st.expander(f"⚙️ {current_session['char_name']} 설정 수정", expanded=False):
            new_inst = st.text_area("현재 지침", value=current_session['instruction'], height=100)
            if st.button("수정 내용 영구 반영"):
                supabase.table("chat_sessions").update({"instruction": new_inst}).eq("id", sid).execute()
                st.success("DB에 저장되었습니다.")
                st.rerun()

        # DB에서 대화 기록 불러오기 (영구 저장의 핵심)
        messages = load_messages(sid)
        for m in messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        if prompt := st.chat_input("메시지를 입력하세요..."):
            # 1. 사용자 메시지 표시 및 DB 저장
            with st.chat_message("user"):
                st.write(prompt)
            save_message(sid, "user", prompt)
            
            # 2. AI 응답 생성
            config_map = {
                "BASIC": {"temp": 0.7, "top_p": 0.9},
                "PRO": {"temp": 0.3, "top_p": 0.8},
                "STORY": {"temp": 1.1, "top_p": 0.95},
                "ROLLPLAYING": {"temp": 0.9, "top_p": 1.0}
            }
            conf = config_map[sai_mode]
            
            # 컨텍스트 구성을 위해 최근 메시지 로드
            history = [{"role": m["role"], "parts": [m["content"]]} for m in messages[-15:]]

            try:
                response = client.models.generate_content(
                    model=selected_model.split("/")[-1],
                    contents=prompt, # 혹은 history를 포함한 복합 구성
                    config=types.GenerateContentConfig(
                        system_instruction=current_session['instruction'],
                        temperature=conf['temp'],
                        top_p=conf['top_p']
                    )
                )
                ai_text = response.text
                
                # 3. AI 응답 표시 및 DB 저장
                with st.chat_message("assistant"):
                    st.write(ai_text)
                save_message(sid, "assistant", ai_text)
                
            except Exception as e:
                st.error(f"오류: {e}")

# [트렌드 탭] 캐릭터 선택 시 새로운 세션 생성 로직
with tabs[1]:
    st.header("🔥 인기 캐릭터")
    chars = supabase.table("sai_characters").select("*").execute().data
    for char in chars:
        if st.button(f"시작하기: {char['name']}", key=f"trend_{char['id']}"):
            # 새로운 세션을 DB에 생성
            new_session = supabase.table("chat_sessions").insert({
                "char_name": char['name'],
                "instruction": char['instruction']
            }).execute()
            st.session_state.current_session_id = new_session.data[0]['id']
            st.rerun()

# [제작소 탭] (기존과 동일)
with tabs[2]:
    st.header("🛠️ 캐릭터 제작소")
    with st.form("make"):
        name = st.text_input("이름")
        inst = st.text_area("지침")
        if st.form_submit_button("저장"):
            supabase.table("sai_characters").insert({"name": name, "instruction": inst}).execute()
            st.success("캐릭터가 등록되었습니다!")
