import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
from streamlit_javascript import st_javascript

# --- [1. 설정 및 API 연결] ---
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide", page_icon="🤖")

# API 키 (본인의 키로 반드시 교체!)
SUPABASE_URL = "https://wkkpssqhumrzaotnkdse.supabase.co"
SUPABASE_KEY = "sb_publishable_L7CYoxdI5y8LCnYzcKvHAQ__3CVUYwH"
GEMINI_API_KEY = "AIzaSyDNpEi4mhiWbGpN8ef-Dv50PiX7am1n7xw"

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
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

# --- [3. 세션 초기화 및 함수] ---
if "chat_partner" not in st.session_state:
    st.session_state.chat_partner = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

def get_ai_response(instruction, user_input, image=None):
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=instruction)
    content = [user_input]
    if image: content.append(image)
    return model.generate_content(content).text

def get_suggestions(ai_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"사용자가 할 짧은 응답 3개를 리스트로. 예: ['응', '아니', '더해']. 대화: {ai_text}"
    try:
        res = model.generate_content(prompt)
        return eval(res.text)
    except:
        return ["계속해줘", "재밌어", "그렇구나"]

# --- [4. UI 및 채팅] ---
st.markdown('<div class="main-logo">SAI</div>', unsafe_allow_html=True)
t1, t2, t3, t4 = st.tabs(["🏠 홈", "🔥 트렌드", "🛠️ 제작", "💬 채팅"])

with t2: # 트렌드 탭 예시
    st.markdown('<div class="sai-card"><img src="https://via.placeholder.com/300" class="sai-img"><h3>AI 친구</h3></div>', unsafe_allow_html=True)
    if st.button("대화하기"):
        st.session_state.chat_partner = {"name": "AI 친구", "inst": "너는 다정한 친구야. '이름: 내용' 형식으로 답해."}
        st.session_state.messages = []
        st.rerun()

with t4: # 채팅 탭
    if st.session_state.chat_partner:
        cp = st.session_state.chat_partner
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])
        
        if prompt := st.chat_input("메시지 입력..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            with st.chat_message("assistant"):
                ans = get_ai_response(cp['inst'], prompt)
                st.write(ans)
                st.session_state.messages.append({"role": "assistant", "content": ans})
                st.session_state.suggestions = get_suggestions(ans)
                st.rerun()