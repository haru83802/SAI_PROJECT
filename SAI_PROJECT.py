import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
from streamlit_javascript import st_javascript

# --- [1. 설정 및 API 연결] ---
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide", page_icon="🤖")

# ⚠️ API 키를 반드시 따옴표("") 안에 넣으세요.
SUPABASE_URL = "https://your-project-url.supabase.co"
SUPABASE_KEY = "your-anon-key"
GEMINI_API_KEY = "your-gemini-key"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"연결 오류: {e}")

# --- [2. CSS 디자인] ---
st.markdown("""
<style>
    .sai-card {
        border-radius: 20px; padding: 20px; background-color: #ffffff;
        border: 1px solid #f0f0f0; box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-bottom: 25px; text-align: center;
    }
    .sai-img {
        width: 100%; aspect-ratio: 1 / 1; object-fit: cover;
        border-radius: 15px; margin-bottom: 15px;
    }
    .main-logo { color: #6e8efb; font-size: 3.5rem; font-weight: 900; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- [3. 세션 및 함수 정의] ---
if "chat_partner" not in st.session_state: st.session_state.chat_partner = None
if "messages" not in st.session_state: st.session_state.messages = []
if "suggestions" not in st.session_state: st.session_state.suggestions = []

user_ip = st_javascript("await fetch('https://api.ipify.org?format=json').then(res => res.json()).then(data => data.ip)")

# AI 답변 생성 함수
def get_ai_response(instruction, user_input, image=None):
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=instruction)
    content = [user_input]
    if image: content.append(image)
    return model.generate_content(content).text

# 추천 답변 생성 함수 (이름을 get_suggestions로 통일)
def get_suggestions(ai_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"다음 답변에 이어질 짧은 응답 3개를 리스트로만 써줘. 예: ['응!', '왜?', '더 말해줘']. 답변: {ai_text}"
    try:
        res = model.generate_content(prompt)
        return eval(res.text)
    except:
        return ["계속해줘", "그렇구나", "재밌어!"]

# --- [4. UI 구성] ---
st.markdown('<div class="main-logo">SAI</div>', unsafe_allow_html=True)
tabs = st.tabs(["🏠 홈", "🔥 트렌드", "🛠️ 제작", "💬 채팅"])

with tabs[0]:
    st.header("나와 AI 사이, SAI")
    st.write("나만의 AI 캐릭터와 1:1 채팅을 즐겨보세요.")

with tabs[1]:
    st.header("🏆 인기 캐릭터")
    cols = st.columns(2)
    with cols[0]:
        st.markdown('<div class="sai-card"><img src="https://via.placeholder.com/300" class="sai-img"><h3>현자</h3></div>', unsafe_allow_html=True)
        if st.button("현자와 대화하기"):
            st.session_state.chat_partner = {"name": "현자", "inst": "너는 현자야. '현자: 내용' 형식으로 답해."}
            st.session_state.messages = []
            st.rerun()

with tabs[2]:
    st.header("🛠️ 제작")
    with st.form("create"):
        name = st.text_input("이름")
        inst = st.text_area("설정 (최대 3만 자)", max_chars=30000)
        if st.form_submit_button("등록"):
            st.success("등록되었습니다!")

with tabs[3]:
    if not st.session_state.chat_partner:
        st.warning("캐릭터를 먼저 선택하세요.")
    else:
        cp = st.session_state.chat_partner
        st.subheader(f"💬 {cp['name']} 사이")

        # 채팅 로그
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])

        # 추천 답변 버튼 표시
        if st.session_state.suggestions:
            cols = st.columns(3)
            for idx, sug in enumerate(st.session_state.suggestions):
                if cols[idx].button(sug):
                    # 버튼 클릭 시 동작은 추가 구현 가능
                    pass

        # 메시지 입력
        if prompt := st.chat_input("메시지를 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)

            with st.chat_message("assistant"):
                response = get_ai_response(cp['inst'], prompt)
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 에러가 났던 부분: 이제 get_suggestions로 이름이 맞습니다.
                st.session_state.suggestions = get_suggestions(response)
                st.rerun()