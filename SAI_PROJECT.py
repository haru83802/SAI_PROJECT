import streamlit as st
from supabase import create_client, Client
from google import genai
from google.genai import types
import uuid
import time

# --- [1. 시스템 설정 및 연결] ---
st.set_page_config(page_title="SAI AI ENGINE", layout="wide")

try:
    # Streamlit Secrets에서 정보를 가져옵니다.
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"연결 오류: {e}. Secrets 설정을 확인하세요.")
    st.stop()

# 세션 상태 초기화
if "current_sid" not in st.session_state:
    st.session_state.current_sid = None

# --- [2. 사이드바: 엔진 및 세션 관리] ---
with st.sidebar:
    st.title("🤖 SAI AI ENGINE")
    
    # SAI 모델 타입 (기획하신 특성 반영)
    sai_mode = st.radio(
        "SAI 모드 선택", 
        ["BASIC", "PRO", "STORY", "ROLLPLAYING"],
        help="PRO: 지시이행력↑, STORY: 기억력↑, RP: 자유도↑"
    )
    
    # 엔진 선택 (404 에러 방지를 위해 models/ 접두사 없이 관리)
    model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
    selected_base = st.selectbox("기반 엔진 선택", model_options)
    target_engine = selected_base.replace("models/", "")

    st.divider()
    if st.button("➕ 새 대화 시작", use_container_width=True):
        st.session_state.current_sid = None
        st.rerun()

    st.subheader("📝 내 대화 목록 (영구 저장)")
    try:
        sessions = supabase.table("chat_sessions").select("*").order("created_at", desc=True).execute().data
        for s in sessions:
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                if st.button(f"💬 {s['char_name']}", key=s['id'], use_container_width=True):
                    st.session_state.current_sid = s['id']
                    st.rerun()
            with col2:
                # 삭제 기능 (선택사항)
                if st.button("🗑️", key=f"del_{s['id']}"):
                    supabase.table("chat_sessions").delete().eq("id", s['id']).execute()
                    st.rerun()
    except:
        st.write("대화 목록을 불러올 수 없습니다.")

# --- [3. 메인 콘텐츠 탭] ---
tabs = st.tabs(["💬 SAI 채팅창", "🔥 트렌드", "🛠️ 제작소"])

# [TAB 0: 채팅창]
with tabs[0]:
    sid = st.session_state.current_sid
    if not sid:
        st.info("👈 사이드바에서 대화방을 선택하거나 신규 캐릭터를 제작하세요.")
    else:
        # DB에서 현재 세션 정보 및 메시지 로드
        chat_info = supabase.table("chat_sessions").select("*").eq("id", sid).single().execute().data
        
        # [실시간 지침 수정 지도 - 컨트롤러]
        with st.expander(f"⚙️ {chat_info['char_name']} 지침 실시간 수정", expanded=False):
            st.caption("대화 도중 캐릭터의 성격이나 설정을 즉시 변경할 수 있습니다.")
            upd_inst = st.text_area("현재 지침 (Prompt)", value=chat_info['instruction'], height=150)
            if st.button("설정 업데이트 및 영구 반영"):
                supabase.table("chat_sessions").update({"instruction": upd_inst}).eq("id", sid).execute()
                st.success("캐릭터 설정이 변경되었습니다.")
                st.rerun()

        st.divider()

        # 메시지 히스토리 출력 (영구 저장된 데이터)
        msgs = supabase.table("chat_messages").select("*").eq("session_id", sid).order("created_at").execute().data
        for m in msgs:
            with st.chat_message(m["role"]):
                st.write(f"**{m.get('speaker_name', m['role'])}**: {m['content']}")

        # 채팅 입력창
        if prompt := st.chat_input("메시지를 입력하세요..."):
            # 1. 사용자 메시지 표시 및 DB 저장
            st.chat_message("user").write(prompt)
            supabase.table("chat_messages").insert({
                "session_id": sid, 
                "role": "user", 
                "speaker_name": "User",
                "content": prompt
            }).execute()

            # 2. SAI 엔진 설정 (모드별 파라미터 분기)
            configs = {
                "BASIC": {"temp": 0.7, "p": 0.9, "k": 40},
                "PRO": {"temp": 0.3, "p": 0.8, "k": 20},      # 지시 준수 강화
                "STORY": {"temp": 1.2, "p": 0.95, "k": 60},   # 창의성 및 묘사 강화
                "ROLLPLAYING": {"temp": 1.0, "p": 1.0, "k": 50} # 반응 가변성 강화
            }
            c = configs[sai_mode]

            try:
                # 3. AI 응답 생성
                # (STORY 모드는 더 긴 컨텍스트를 유지하도록 설계 가능)
                res = client.models.generate_content(
                    model=target_engine,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=chat_info['instruction'],
                        temperature=c['temp'],
                        top_p=c['p'],
                        top_k=c['k'],
                        max_output_tokens=2000 if sai_mode == "STORY" else 1000
                    )
                )
                ai_text = res.text
                
                # 4. AI 응답 표시 및 DB 저장
                with st.chat_message("assistant"):
                    st.write(f"**{chat_info['char_name']}**: {ai_text}")
                
                supabase.table("chat_messages").insert({
                    "session_id": sid, 
                    "role": "assistant", 
                    "speaker_name": chat_info['char_name'],
                    "content": ai_text
                }).execute()
                    
            except Exception as e:
                # 429 Resource Exhausted 에러 및 기타 에러 처리
                if "429" in str(e):
                    st.error("🚨 API 할당량 초과! 무료 티어 제한으로 인해 약 1분 후 다시 시도해주세요.")
                else:
                    st.error(f"❌ 엔진 에러: {e}")

# [TAB 1: 트렌드]
with tabs[1]:
    st.header("🔥 인기 캐릭터 트렌드")
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        cols = st.columns(2)
        for idx, char in enumerate(chars):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.subheader(char['name'])
                    st.text(char['instruction'][:100] + "...")
                    if st.button(f"{char['name']}와 대화 시작", key=f"tr_{char['id']}"):
                        # 새 세션 생성
                        new_s = supabase.table("chat_sessions").insert({
                            "char_name": char['name'],
                            "instruction": char['instruction']
                        }).execute()
                        st.session_state.current_sid = new_s.data[0]['id']
                        st.rerun()
    except:
        st.info("등록된 캐릭터가 없습니다. 제작소에서 첫 캐릭터를 만들어보세요!")

# [TAB 2: 제작소]
with tabs[2]:
    st.header("🛠️ SAI 캐릭터 제작소")
    with st.form("char_make_form"):
        new_name = st.text_input("캐릭터 이름", placeholder="예: 냉소적인 마법사")
        new_inst = st.text_area("캐릭터 상세 지침 (Prompt)", placeholder="성격, 말투, 세계관 등을 입력하세요.")
        submit = st.form_submit_button("캐릭터 생성 및 저장")
        
        if submit and new_name and new_inst:
            # 1. 템플릿 저장
            supabase.table("sai_characters").insert({"name": new_name, "instruction": new_inst}).execute()
            # 2. 즉시 대화 세션 생성
            new_session = supabase.table("chat_sessions").insert({
                "char_name": new_name,
                "instruction": new_inst
            }).execute()
            st.session_state.current_sid = new_session.data[0]['id']
            st.success(f"{new_name} 캐릭터가 생성되었습니다!")
            st.rerun()
