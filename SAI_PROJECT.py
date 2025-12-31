import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from security import sai_guard
import uuid

# [보안 시스템: IP 차단 확인]
if sai_guard.is_banned():
    st.error("🚫 당신의 IP는 보안 위협으로 인해 시스템에서 차단되었습니다.")
    st.stop()

# [기본 설정]
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("설정 오류: Secrets를 확인해주세요.")
    st.stop()

# [세션 관리]
if "user" not in st.session_state: st.session_state.user = None
if "chat_partner" not in st.session_state: st.session_state.chat_partner = None
if "messages" not in st.session_state: st.session_state.messages = []

# --- [사이드바: 로그인 & 회원가입] ---
with st.sidebar:
    st.title("👤 SAI 계정 센터")
    
    if st.session_state.user is None:
        email = st.text_input("이메일", placeholder="example@email.com")
        pw = st.text_input("비밀번호", type="password")
        
        c1, c2 = st.columns(2)
        if c1.button("로그인", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("정보를 확인하세요.")
        
        if c2.button("회원가입", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": email, "password": pw})
                st.success("확인 메일을 보냈습니다!")
            except: st.error("가입 실패 (이미 있는 이메일 등)")
            
        st.divider()
        st.write("🌟 간편 로그인")
        google_url = f"{st.secrets['SUPABASE_URL']}/auth/v1/authorize?provider=google&redirect_to=https://withsai-ai-io.streamlit.app"
        st.link_button("🚀 구글로 시작하기", google_url, use_container_width=True)
    else:
        st.success(f"**{st.session_state.user.email}**님")
        if st.button("로그아웃", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

# --- [메인 기능: 탭 구성] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 캐릭터 선택 (이미지 표시)]
with tabs[0]:
    st.subheader("인기 캐릭터")
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        cols = st.columns(3)
        for i, char in enumerate(chars):
            with cols[i % 3]:
                if char.get('image_url'): # 이미지가 있으면 표시
                    st.image(char['image_url'], width=150)
                st.info(f"**{char['name']}**")
                st.caption(char['description'])
                if char.get('creator_comment'): # 제작자 코멘트 표시
                    st.markdown(f"*{char['creator_comment']}*")
                if st.button("대화하기", key=f"sel_{char['id']}"):
                    st.session_state.chat_partner = char
                    st.session_state.messages = []
                    st.success(f"{char['name']} 선택됨!")
    except: st.write("캐릭터를 불러오는 중...")

# [탭 2: 채팅창]
with tabs[1]:
    if not st.session_state.chat_partner:
        st.warning("먼저 '트렌드' 탭에서 캐릭터를 선택해주세요.")
    else:
        cp = st.session_state.chat_partner
        st.subheader(f"💬 {cp['name']}와 대화")
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        if prompt := st.chat_input(f"{cp['name']}에게 메시지 보내기"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            # 여기에 AI 응답 로직 추가 (Gemini)
            with st.chat_message("assistant"):
                # 실제 Gemini API 호출 및 응답 처리
                response_text = "안녕하세요!" # 임시 응답
                st.write(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            st.rerun()

# [탭 3: 이미지 공유]
with tabs[2]:
    st.header("📸 이미지 게시판")
    if st.session_state.user:
        with st.expander("이미지 올리기"):
            file = st.file_uploader("사진 선택", type=['png', 'jpg', 'jpeg'])
            desc = st.text_input("설명")
            if st.button("업로드"):
                if file:
                    fname = f"{uuid.uuid4()}.png"
                    supabase.storage.from_("images").upload(fname, file.read())
                    url = supabase.storage.from_("images").get_public_url(fname)
                    supabase.table("posts").insert({"user_id":st.session_state.user.id, "img_url":url, "description":desc}).execute()
                    st.rerun()
                else: st.warning("파일을 선택해주세요.")
    
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts:
        st.image(p['img_url'], caption=p['description'], width=400)
        st.divider()

# [탭 4: 커뮤니티 댓글]
with tabs[3]:
    st.header("📝 자유 댓글창")
    if st.session_state.user:
        with st.form("comment_f", clear_on_submit=True):
            txt = st.text_area("내용 입력")
            if st.form_submit_button("등록"):
                safe_content = sai_guard.sanitize_text(txt)
                is_ok, err_msg = sai_guard.check_malicious(safe_content)
                if is_ok:
                    supabase.table("comments").insert({"user_email":st.session_state.user.email, "content":safe_content}).execute()
                    st.rerun()
                else: st.error(err_msg)
    
    comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
    for c in comments:
        with st.container(border=True):
            st.write(f"**{c['user_email']}**")
            st.write(c['content'])
            st.caption(f"작성일: {c['created_at']}")
            st.divider()

# [탭 5: 캐릭터 제작 (이미지, 코멘트 추가됨)]
with tabs[4]:
    st.header("🛠️ 나만의 SAI 만들기")
    if not st.session_state.user:
        st.error("로그인이 필요합니다.")
    else:
        with st.form("create_char"):
            c_name = st.text_input("캐릭터 이름")
            c_desc = st.text_input("한줄 소개")
            c_ins = st.text_area("AI의 성격과 말투를 자세히 적어주세요 (지침)", height=150)
            
            # [새로 추가된 기능] 캐릭터 대표 이미지 업로드
            char_image = st.file_uploader("캐릭터 대표 이미지 (선택)", type=['png', 'jpg', 'jpeg'])
            # [새로 추가된 기능] 제작자 코멘트
            creator_comment = st.text_area("제작자 한마디 (최대 200자)", max_chars=200)

            if st.form_submit_button("캐릭터 생성"):
                if c_name and c_ins:
                    image_url = None
                    if char_image: # 이미지가 있다면 Storage에 업로드
                        image_fname = f"char_{uuid.uuid4()}.png"
                        supabase.storage.from_("images").upload(image_fname, char_image.read())
                        image_url = supabase.storage.from_("images").get_public_url(image_fname)

                    supabase.table("sai_characters").insert({
                        "name": c_name, 
                        "description": c_desc, 
                        "instruction": c_ins,
                        "image_url": image_url, # 이미지 URL 저장
                        "creator_comment": sai_guard.sanitize_text(creator_comment) # 코멘트 저장
                    }).execute()
                    st.success("새 캐릭터가 생성되었습니다! '트렌드' 탭을 확인하세요.")
                else:
                    st.warning("이름과 지침을 입력하세요.")