import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from security import sai_guard
import uuid

# --- [0. 시스템 초기화 및 보안 체크] ---
# 세션 상태가 없으면 가장 먼저 생성 (KeyError 방지)
if "banned_ips" not in st.session_state:
    st.session_state.banned_ips = set()
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_partner" not in st.session_state:
    st.session_state.chat_partner = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# IP 차단 여부 확인
if sai_guard.is_banned():
    st.error("🚫 보안 위협으로 인해 차단된 IP입니다. 시스템에 접근할 수 없습니다.")
    st.stop()

# --- [1. 기본 설정 및 DB 연결] ---
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"환경 변수 로드 실패: {e}")
    st.stop()

# --- [2. 사이드바: 로그인/회원가입] ---
with st.sidebar:
    st.title("👤 SAI 계정 센터")
    if st.session_state.user is None:
        email = st.text_input("이메일")
        pw = st.text_input("비밀번호", type="password")
        col1, col2 = st.columns(2)
        
        if col1.button("로그인", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("로그인 실패")
            
        if col2.button("회원가입", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": email, "password": pw})
                st.success("메일함을 확인하세요!")
            except: st.error("가입 실패")
    else:
        st.success(f"**{st.session_state.user.email}**님")
        if st.button("로그아웃", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

# --- [3. 메인 콘텐츠: 탭 구성] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드 - 캐릭터 목록]
with tabs[0]:
    st.subheader("인기 캐릭터")
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        cols = st.columns(3)
        for i, char in enumerate(chars):
            with cols[i % 3]:
                if char.get('image_url'):
                    st.image(char['image_url'], use_container_width=True)
                st.info(f"**{char['name']}**")
                st.write(char['description'])
                if char.get('creator_comment'):
                    st.caption(f"💭 제작자: {char['creator_comment']}")
                if st.button("대화하기", key=f"char_{char['id']}"):
                    st.session_state.chat_partner = char
                    st.session_state.messages = []
                    st.success(f"{char['name']}와 연결되었습니다!")
    except: st.write("캐릭터가 없습니다. 먼저 제작해 보세요!")

# [탭 2: 채팅창]
with tabs[1]:
    if not st.session_state.chat_partner:
        st.warning("트렌드 탭에서 대화할 캐릭터를 선택해 주세요.")
    else:
        cp = st.session_state.chat_partner
        st.subheader(f"💬 {cp['name']}와의 대화")
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])
        
        if prompt := st.chat_input("메시지를 입력하세요"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            # AI 응답 로직 (여기에 Gemini 호출 코드를 넣으세요)
            st.rerun()

# [탭 3: 이미지 게시판]
with tabs[2]:
    st.header("📸 이미지 공유")
    if st.session_state.user:
        with st.expander("이미지 업로드"):
            img_file = st.file_uploader("파일 선택", type=['png', 'jpg', 'jpeg'])
            img_desc = st.text_input("설명 입력")
            if st.button("업로드"):
                if img_file:
                    fname = f"{uuid.uuid4()}.png"
                    supabase.storage.from_("images").upload(fname, img_file.read())
                    url = supabase.storage.from_("images").get_public_url(fname)
                    supabase.table("posts").insert({"user_id": st.session_state.user.id, "img_url": url, "description": img_desc}).execute()
                    st.rerun()

# [탭 4: 커뮤니티 - 댓글]
with tabs[3]:
    st.header("📝 자유 댓글창")
    if st.session_state.user:
        with st.form("comm_form", clear_on_submit=True):
            content = st.text_area("내용")
            if st.form_submit_button("등록"):
                safe_text = sai_guard.sanitize_text(content)
                is_safe, msg = sai_guard.check_malicious(safe_text)
                if is_safe:
                    supabase.table("comments").insert({"user_email": st.session_state.user.email, "content": safe_text}).execute()
                    st.rerun()
                else: st.error(msg)
    # 댓글 목록
    comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
    for c in comments:
        st.write(f"**{c['user_email']}**: {c['content']}")
        st.divider()

# [탭 5: 캐릭터 제작 (이미지 & 제작자 코멘트 포함)]
with tabs[4]:
    st.header("🛠️ 나만의 SAI 만들기")
    if not st.session_state.user:
        st.error("로그인이 필요합니다.")
    else:
        with st.form("create_form"):
            name = st.text_input("캐릭터 이름")
            desc = st.text_input("한줄 소개")
            ins = st.text_area("AI 행동 지침 (Instruction)")
            char_img = st.file_uploader("캐릭터 대표 이미지", type=['jpg','png','jpeg'])
            comment = st.text_area("제작자 코멘트 (유저들에게 보일 한마디)")
            
            if st.form_submit_button("캐릭터 생성"):
                img_url = None
                if char_img:
                    if char_img.size > 2*1024*1024:
                        st.error("이미지는 2MB 이하여야 합니다.")
                    else:
                        if_name = f"char_{uuid.uuid4()}.png"
                        supabase.storage.from_("images").upload(if_name, char_img.read())
                        img_url = supabase.storage.from_("images").get_public_url(if_name)
                
                supabase.table("sai_characters").insert({
                    "name": name,
                    "description": desc,
                    "instruction": ins,
                    "image_url": img_url,
                    "creator_comment": sai_guard.sanitize_text(comment)
                }).execute()
                st.success("캐릭터가 생성되었습니다! 트렌드 탭을 확인하세요.")