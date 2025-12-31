import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from security import sai_guard
import uuid

# --- [0. 시스템 초기화 및 보안] ---
if "banned_ips" not in st.session_state: st.session_state.banned_ips = set()
if "user" not in st.session_state: st.session_state.user = None
if "chat_partner" not in st.session_state: st.session_state.chat_partner = None
if "messages" not in st.session_state: st.session_state.messages = []

if sai_guard.is_banned():
    st.error("🚫 보안 위협으로 인해 차단된 IP입니다.")
    st.stop()

# --- [1. 설정 및 연결] ---
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide", page_icon="🤖")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("설정 오류: Secrets 보관함을 확인하세요.")
    st.stop()

# --- [2. 사이드바: 계정 관리] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    st.caption("우리 사이를 잇는 AI 서비스")
    
    if st.session_state.user is None:
        st.write("---")
        with st.expander("🔐 로그인 / 회원가입"):
            email = st.text_input("이메일")
            pw = st.text_input("비밀번호", type="password")
            c1, c2 = st.columns(2)
            if c1.button("로그인", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("정보 오류")
            if c2.button("회원가입", use_container_width=True):
                try: supabase.auth.sign_up({"email": email, "password": pw})
                except: st.error("가입 실패")
    else:
        st.success(f"✅ {st.session_state.user.email}")
        if st.button("로그아웃"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

# --- [3. 메인 화면: 로고 및 공지사항] ---
st.title("🌐 SAI : 우리 사이 AI")

# [공지사항 섹션] - 텍스트로 깔끔하게 구성
with st.container():
    st.markdown("### 📢 SAI 공지사항")
    notice_text = """
    * **[업데이트]** 캐릭터 제작 시 이미지 업로드 및 제작자 코멘트 기능이 추가되었습니다! 📸
    * **[안내]** 로그인 없이도 모든 기능을 'Guest'로 자유롭게 이용하실 수 있습니다. 🔓
    * **[매너]** 건전한 커뮤니티를 위해 비속어 및 악성 게시글은 보안 시스템에 의해 자동 차단될 수 있습니다. 🛡️
    """
    st.info(notice_text)

st.write("---") # 구분선

# --- [4. 메인 기능 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드]
with tabs[0]:
    st.subheader("인기 AI 캐릭터")
    chars = supabase.table("sai_characters").select("*").execute().data
    if not chars:
        st.write("생성된 캐릭터가 없습니다. '캐릭터 제작' 탭에서 첫 캐릭터를 만들어보세요!")
    else:
        cols = st.columns(3)
        for i, char in enumerate(chars):
            with cols[i % 3]:
                if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                st.info(f"**{char['name']}**")
                st.write(char['description'])
                if char.get('creator_comment'): st.caption(f"💭 {char['creator_comment']}")
                if st.button("대화하기", key=f"c_{char['id']}"):
                    st.session_state.chat_partner = char
                    st.session_state.messages = []
                    st.success(f"'{char['name']}'와 연결됨!")

# [탭 2: 채팅창]
with tabs[1]:
    if not st.session_state.chat_partner:
        st.warning("먼저 '트렌드' 탭에서 대화할 캐릭터를 선택해 주세요.")
    else:
        cp = st.session_state.chat_partner
        st.subheader(f"💬 {cp['name']}와 대화 중")
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])
            
        if prompt := st.chat_input("메시지를 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            # Gemini AI 응답
            model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=cp['instruction'])
            response = model.generate_content(prompt)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()

# [탭 3: 이미지 게시판]
with tabs[2]:
    st.header("📸 이미지 공유")
    with st.expander("사진 올리기"):
        f = st.file_uploader("사진 선택", type=['jpg','png','jpeg'])
        d = st.text_input("설명")
        if st.button("게시"):
            if f:
                fn = f"img_{uuid.uuid4()}.png"
                supabase.storage.from_("images").upload(fn, f.read())
                url = supabase.storage.from_("images").get_public_url(fn)
                u_id = st.session_state.user.id if st.session_state.user else "00000000-0000-0000-0000-000000000000"
                supabase.table("posts").insert({"user_id": u_id, "img_url": url, "description": d}).execute()
                st.rerun()
    
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts:
        st.image(p['img_url'], caption=p['description'], width=400)
        st.divider()

# [탭 4: 커뮤니티 댓글]
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("comm_form", clear_on_submit=True):
        txt = st.text_area("의견을 남겨주세요")
        if st.form_submit_button("등록"):
            name = st.session_state.user.email if st.session_state.user else "Guest(익명)"
            supabase.table("comments").insert({"user_email": name, "content": txt}).execute()
            st.rerun()
    
    for c in supabase.table("comments").select("*").order("created_at", desc=True).execute().data:
        st.write(f"**{c['user_email']}**: {c['content']}")
        st.caption(f"작성일: {c['created_at']}")
        st.divider()

# [탭 5: 캐릭터 제작]
with tabs[4]:
    st.header("🛠️ 캐릭터 제작 센터")
    with st.form("make_char"):
        n = st.text_input("캐릭터 이름")
        d = st.text_input("한줄 소개")
        i = st.text_area("행동 지침 (AI 말투와 성격)")
        img = st.file_uploader("대표 이미지 (추천)", type=['jpg','png'])
        comm = st.text_area("제작자 코멘트")
        
        if st.form_submit_button("SAI 캐릭터 생성"):
            if n and i:
                img_url = None
                if img:
                    if_n = f"char_{uuid.uuid4()}.png"
                    supabase.storage.from_("images").upload(if_n, img.read())
                    img_url = supabase.storage.from_("images").get_public_url(if_n)
                
                creator = st.session_state.user.email if st.session_state.user else "Guest"
                supabase.table("sai_characters").insert({
                    "name": n, "description": d, "instruction": i,
                    "image_url": img_url, "creator_comment": f"By {creator}: {comm}"
                }).execute()
                st.success("캐릭터 제작 완료! '트렌드' 탭에서 확인하세요.")
            else:
                st.error("이름과 지침은 필수입니다.")