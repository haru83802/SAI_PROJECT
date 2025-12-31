import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image

# --- [1. 기본 설정 및 보안 연결] ---
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide", page_icon="🤖")

# 로컬 테스트용 직접 입력 또는 Streamlit Cloud Secrets 사용
# 로컬에서 쓸 때는 "내키" 부분에 직접 넣고, 배포할 땐 st.secrets를 사용하세요.
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://your-project.supabase.co")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "your-anon-key")
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "your-gemini-key")
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
except:
    st.error("API 키 설정이 필요합니다. Settings > Secrets를 확인하세요.")

# --- [2. CSS 디자인] ---
st.markdown("""
<style>
    .sai-card {
        border-radius: 20px; padding: 20px; background-color: #ffffff;
        border: 1px solid #f0f0f0; box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-bottom: 25px; text-align: center; height: 100%;
    }
    .sai-img {
        width: 100%; aspect-ratio: 1 / 1; object-fit: cover;
        border-radius: 15px; margin-bottom: 15px;
    }
    .main-logo { color: #6e8efb; font-size: 3.5rem; font-weight: 900; text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- [3. 세션 상태 관리] ---
if "user" not in st.session_state: st.session_state.user = None
if "chat_partner" not in st.session_state: st.session_state.chat_partner = None
if "messages" not in st.session_state: st.session_state.messages = []
if "suggestions" not in st.session_state: st.session_state.suggestions = []

# --- [4. 유틸리티 함수] ---
def get_ai_response(instruction, user_input):
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=instruction)
    return model.generate_content(user_input).text

def get_suggestions(ai_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"다음 답변에 이어질 짧은 반응 3개를 리스트로만 써줘. 예: ['응!', '왜?', '더 말해줘']. 대화: {ai_text}"
    try:
        res = model.generate_content(prompt)
        return eval(res.text)
    except: return ["계속해", "대박", "글쿤"]

# --- [5. 사이드바 로그인 UI] ---
with st.sidebar:
    st.title("👤 계정")
    if st.session_state.user is None:
        email = st.text_input("이메일")
        pw = st.text_input("비밀번호", type="password")
        col1, col2 = st.columns(2)
        if col1.button("로그인"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("로그인 실패")
        if col2.button("회원가입"):
            supabase.auth.sign_up({"email": email, "password": pw})
            st.info("이메일을 확인하세요!")
    else:
        st.write(f"**{st.session_state.user.email}**님")
        if st.button("로그아웃"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

# --- [6. 메인 UI 구성] ---
st.markdown('<div class="main-logo">SAI</div>', unsafe_allow_html=True)
tabs = st.tabs(["🏠 홈", "🔍 검색", "🔥 트렌드", "🛠️ 제작", "💬 채팅"])

# --- TAB 1: 홈 & 공지 ---
with tabs[0]:
    st.info("📢 [공지] 24시간 서버 가동 시작! 이제 언제든 SAI를 만나보세요.")
    st.header("우리 사이 AI, SAI")
    if st.session_state.user:
        st.subheader("나의 활동")
        c1, c2 = st.columns(2)
        c1.metric("팔로잉", "12")
        c2.metric("팔로워", "48")

# --- TAB 2: 검색 및 팔로우 ---
with tabs[1]:
    st.header("🔍 SAI 찾기")
    search = st.text_input("이름으로 검색하세요")
    res = supabase.table("sai_characters").select("*").execute()
    chars = [c for c in res.data if search.lower() in c['name'].lower()]
    
    for c in chars:
        col1, col2, col3 = st.columns([1, 3, 1])
        col1.image(c.get('image_url', "https://via.placeholder.com/150"))
        col2.subheader(c['name'])
        col2.write(c['description'])
        if col3.button("팔로우", key=f"follow_{c['id']}"):
            st.toast(f"{c['name']}님을 팔로우했습니다!")
        st.divider()

# --- TAB 3: 트렌드 (목록) ---
with tabs[2]:
    st.header("🔥 실시간 인기 캐릭터")
    res = supabase.table("sai_characters").select("*").order("created_at", desc=True).execute()
    cols = st.columns(3)
    for i, char in enumerate(res.data):
        with cols[i % 3]:
            st.markdown(f'''<div class="sai-card">
                <img src="{char.get('image_url', 'https://via.placeholder.com/300')}" class="sai-img">
                <h4>{char['name']}</h4><p>{char['description']}</p></div>''', unsafe_allow_html=True)
            if st.button(f"{char['name']}와 대화", key=f"chat_{char['id']}"):
                st.session_state.chat_partner = char
                st.session_state.messages = []
                st.rerun()

# --- TAB 4: 제작 (3만 자 페르소나) ---
with tabs[3]:
    st.header("🛠️ SAI 캐릭터 제작")
    with st.form("create_form"):
        name = st.text_input("캐릭터 이름")
        desc = st.text_input("한 줄 소개")
        inst = st.text_area("프롬프트 설정 (최대 30,000자)", height=300, max_chars=30000)
        if st.form_submit_button("등록하기"):
            if name and inst:
                supabase.table("sai_characters").insert({
                    "name": name, "description": desc, "instruction": inst,
                    "image_url": "https://via.placeholder.com/300"
                }).execute()
                st.success("등록 완료!")
            else: st.warning("내용을 입력해주세요.")

# --- TAB 5: 채팅 (Gemini) ---
with tabs[4]:
    if not st.session_state.chat_partner:
        st.warning("먼저 캐릭터를 선택해주세요.")
    else:
        cp = st.session_state.chat_partner
        st.subheader(f"💬 {cp['name']}와 대화 중")
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])
            
        if prompt := st.chat_input("메시지 입력..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            with st.chat_message("assistant"):
                ans = get_ai_response(cp['instruction'], prompt)
                st.write(ans)
                st.session_state.messages.append({"role": "assistant", "content": ans})
                st.session_state.suggestions = get_suggestions(ans)
                st.rerun()