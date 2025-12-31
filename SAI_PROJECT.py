import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
from streamlit_javascript import st_javascript

# --- [1. 기본 설정 및 API 연결] ---
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide", page_icon="🤖")

# ⚠️ 본인의 실제 키로 교체하세요 (따옴표 필수)
SUPABASE_URL = "https://wkkpssqhumrzaotnkdse.supabase.co"
SUPABASE_KEY = "sb_publishable_L7CYoxdI5y8LCnYzcKvHAQ__3CVUYwH"
GEMINI_API_KEY = "AIzaSyDNpEi4mhiWbGpN8ef-Dv50PiX7am1n7xw"
@st.cache_resource
def init_connection():
    try:
        s_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        genai.configure(api_key=GEMINI_API_KEY)
        return s_client
    except Exception as e:
        st.error(f"연결 오류: {e}")
        return None

supabase = init_connection()

# --- [2. CSS 디자인 (1:1 이미지 레이아웃)] ---
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
    .main-logo { color: #6e8efb; font-size: 3.5rem; font-weight: 900; text-align: center; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- [3. 세션 상태 관리] ---
if "chat_partner" not in st.session_state: st.session_state.chat_partner = None
if "messages" not in st.session_state: st.session_state.messages = []
if "suggestions" not in st.session_state: st.session_state.suggestions = []

# --- [4. 로직 함수] ---
def get_ai_response(instruction, user_input):
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=instruction)
    response = model.generate_content(user_input)
    return response.text

def get_suggestions(ai_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"다음 답변에 이어질 짧은 대답 3개를 리스트로만 써줘. 예: ['응!', '왜?', '더 말해줘']. 대화: {ai_text}"
    try:
        res = model.generate_content(prompt)
        return eval(res.text)
    except:
        return ["계속해줘", "그렇구나", "재밌어!"]

# --- [5. 메인 UI 및 탭 구성] ---
st.markdown('<div class="main-logo">SAI</div>', unsafe_allow_html=True)
tabs = st.tabs(["🏠 홈", "🔥 트렌드", "🛠️ 제작", "💬 채팅"])

# --- TAB 1: 홈 ---
with tabs[0]:
    st.header("📢 SAI 공지사항")
    try:
        # DB에서 활성화된(is_active=True) 공지만 가져오기
        notices = supabase.table("sai_notices").select("*").eq("is_active", True).order("created_at", desc=True).execute()
        
        if notices.data:
            for n in notices.data:
                with st.expander(f"📌 {n['title']} ({n['created_at'][:10]})"):
                    st.write(n['content'])
        else:
            st.write("현재 등록된 공지가 없습니다.")
    except Exception as e:
        st.error(f"공지를 불러오는 중 오류 발생: {e}")

# --- TAB 2: 트렌드 (제작된 캐릭터 목록 불러오기) ---
with tabs[1]:
    st.header("🔥 실시간 인기 SAI")
    if supabase:
        try:
            # DB에서 캐릭터 리스트 불러오기
            res = supabase.table("sai_characters").select("*").order("created_at", desc=True).execute()
            chars = res.data
            
            if not chars:
                st.write("아직 등록된 캐릭터가 없습니다. '제작' 탭에서 첫 캐릭터를 만들어보세요!")
            else:
                cols = st.columns(3)
                for idx, char in enumerate(chars):
                    with cols[idx % 3]:
                        st.markdown(f'''
                        <div class="sai-card">
                            <img src="{char.get('image_url', 'https://via.placeholder.com/300')}" class="sai-img">
                            <h4>{char['name']}</h4>
                            <p>{char['description']}</p>
                        </div>
                        ''', unsafe_allow_html=True)
                        if st.button(f"{char['name']}와 대화하기", key=f"btn_{char['id']}"):
                            st.session_state.chat_partner = char
                            st.session_state.messages = []
                            st.success(f"{char['name']}가 선택되었습니다! 채팅 탭으로 이동하세요.")
        except Exception as e:
            st.error(f"데이터 로드 오류: {e}")

# --- TAB 3: 제작 (DB에 저장) ---
with tabs[2]:
    st.header("🛠️ 나만의 SAI 캐릭터 만들기")
    with st.form("create_form", clear_on_submit=True):
        new_name = st.text_input("캐릭터 이름", placeholder="예: 무뚝뚝한 집사")
        new_desc = st.text_input("한 줄 소개", placeholder="성격을 한마디로 요약해주세요.")
        new_inst = st.text_area("페르소나 설정 (최대 30,000자)", height=300, max_chars=30000, 
                               placeholder="어떤 상황에서도 이 성격을 유지하도록 상세히 적어주세요.")
        
        if st.form_submit_button("SAI 캐릭터 등록"):
            if new_name and new_inst:
                save_data = {
                    "name": new_name,
                    "description": new_desc,
                    "instruction": new_inst,
                    "image_url": "https://via.placeholder.com/300" # 추후 Storage 연동 가능
                }
                supabase.table("sai_characters").insert(save_data).execute()
                st.success(f"'{new_name}' 캐릭터 등록 완료! 트렌드 탭에서 확인하세요.")
            else:
                st.warning("이름과 설정을 입력해주세요.")

# --- TAB 4: 채팅 (Gemini 연동) ---
with tabs[3]:
    if not st.session_state.chat_partner:
        st.warning("트렌드 탭에서 대화할 캐릭터를 먼저 선택해주세요.")
    else:
        cp = st.session_state.chat_partner
        st.subheader(f"💬 {cp['name']}와 나 사이")
        
        # 이전 메시지 출력
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        # 추천 답변 버튼
        if st.session_state.suggestions:
            s_cols = st.columns(len(st.session_state.suggestions))
            for i, sug in enumerate(st.session_state.suggestions):
                if s_cols[i].button(sug):
                    # 버튼 클릭 시 해당 텍스트를 입력으로 처리하도록 유도 가능
                    pass

        # 채팅 입력
        if prompt := st.chat_input("메시지를 보내보세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                # 제작 시 입력했던 cp['instruction']을 Gemini에 전달
                response = get_ai_response(cp['instruction'], prompt)
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 추천 답변 갱신
                st.session_state.suggestions = get_suggestions(response)
                st.rerun()