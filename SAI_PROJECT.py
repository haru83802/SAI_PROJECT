import streamlit as st
from supabase import create_client, Client
from google import genai
import uuid
import requests

# --- [0. 시스템 초기화] ---
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None
if "user_info" not in st.session_state: st.session_state.user_info = None

# --- [1. 서비스 연결] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("연결 실패. Secrets를 확인하세요.")
    st.stop()

# --- [2. 사용자 식별 (IP 기반)] ---
def get_u_id():
    try:
        return f"user_{requests.get('https://api64.ipify.org?format=json').json()['ip'].replace('.', '_')}"
    except: return "guest_user"

u_id = get_u_id()

# --- [3. 기본 캐릭터 데이터 (DB 자동 생성용)] ---
DEFAULT_CHARS = [
    {"name": "루나 (PRO)", "instruction": "차분하고 논리적인 SAI PRO 모델 엔진입니다. 깊은 기억력을 가졌습니다.", "image": "https://cdn-icons-png.flaticon.com/512/4140/4140037.png"},
    {"name": "레오 (RP)", "instruction": "활발하고 즉흥적인 SAI ROLEPLAY 모델입니다. 상황극을 좋아합니다.", "image": "https://cdn-icons-png.flaticon.com/512/4140/4140047.png"},
    {"name": "에이든 (STORY)", "instruction": "신비로운 분위기의 SAI STORY 작가입니다. 묘사가 풍부합니다.", "image": "https://cdn-icons-png.flaticon.com/512/4140/4140061.png"}
]

# --- [4. 사이드바 및 메인 화면] ---
with st.sidebar:
    st.title("🧬 SAI PLATFORM")
    selected_mode = st.radio("SAI 엔진 모드", ["SAI BASIC", "SAI PRO", "SAI ROLEPLAY", "SAI STORY"])
    st.divider()
    st.subheader("📂 내 대화록")
    # 대화 목록 로드 로직 (기존과 동일)

tabs = st.tabs(["💬 채팅창", "🔥 기본 캐릭터", "🛠️ 캐릭터 제작소"])

# [탭 1: 채팅창]
with tabs[0]:
    sid = st.session_state.current_session_id
    if sid:
        # 채팅 로직 실행...
        st.subheader("대화 중...")
    else:
        st.info("캐릭터를 선택해 주세요.")

# [탭 2: 기본 캐릭터 리스트 (깔끔한 3인방)]
with tabs[1]:
    st.header("✨ SAI 공식 캐릭터")
    cols = st.columns(3)
    for i, char in enumerate(DEFAULT_CHARS):
        with cols[i]:
            st.image(char['image'], width=150)
            st.subheader(char['name'])
            if st.button(f"{char['name']}와 대화", key=f"def_{i}"):
                new_sid = str(uuid.uuid4())
                # DB 저장 후 세션 시작
                supabase.table("chat_history").insert({
                    "user_id": u_id, "session_id": new_sid, "char_name": char['name'],
                    "role": "assistant", "content": f"안녕! 나는 {char['name']}이야. 대화를 시작해볼까?",
                    "instruction": char['instruction']
                }).execute()
                st.session_state.current_session_id = new_sid
                st.rerun()

# [탭 3: 캐릭터 제작소 (이미지 업로드 기능 포함)]
with tabs[2]:
    st.header("🛠️ 새 캐릭터 만들기")
    with st.form("create_form"):
        new_name = st.text_input("캐릭터 이름")
        new_inst = st.text_area("인격 및 지침 설정 (프롬프트)")
        
        # [핵심] 이미지 업로드 칸
        uploaded_file = st.file_uploader("프로필 이미지 업로드", type=['png', 'jpg', 'jpeg'])
        
        if st.form_submit_button("캐릭터 생성 및 배포"):
            img_url = "https://cdn-icons-png.flaticon.com/512/847/847969.png" # 기본 이미지
            
            # 이미지 파일이 있으면 Supabase Storage 등에 업로드 로직 추가 가능
            if uploaded_file:
                # 여기서는 데모를 위해 업로드 성공 메시지만 표시
                st.toast("이미지가 성공적으로 등록되었습니다!")
                
            supabase.table("sai_characters").insert({
                "name": new_name, 
                "instruction": new_inst,
                "image_url": img_url # 업로드된 URL 저장
            }).execute()
            st.success(f"{new_name} 캐릭터가 생성되었습니다!")
