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

# --- [1. 금고(Secrets)에서 설정 불러오기] ---
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide")

try:
    # streamlit 설정창이나 secrets.toml에 저장된 키를 불러옵니다.
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("설정 오류: Secrets 보관함에 API 키가 있는지 확인하세요.")
    st.stop()

# --- [2. 사이드바: 선택형 계정 관리] ---
with st.sidebar:
    st.title("👤 SAI 계정")
    if st.session_state.user is None:
        st.write("현재 **Guest(익명)** 상태입니다.")
        with st.expander("로그인 / 회원가입"):
            email = st.text_input("이메일")
            pw = st.text_input("비밀번호", type="password")
            c1, c2 = st.columns(2)
            if c1.button("로그인"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("정보가 일치하지 않습니다.")
            if c2.button("회원가입"):
                try: 
                    supabase.auth.sign_up({"email": email, "password": pw})
                    st.info("메일함을 확인해 주세요!")
                except: st.error("가입 실패")
    else:
        st.success(f"✅ {st.session_state.user.email}님")
        if st.button("로그아웃"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

# --- [3. 메인 기능 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드]
with tabs[0]:
    st.subheader("인기 AI 캐릭터")
    chars = supabase.table("sai_characters").select("*").execute().data
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
                st.success(f"{char['name']} 선택됨! 채팅 탭으로 가보세요.")

# [탭 2: 채팅창]
with tabs[1]:
    if not st.session_state.chat_partner:
        st.warning("먼저 캐릭터를 선택해 주세요.")
    else:
        cp = st.session_state.chat_partner
        st.subheader(f"💬 {cp['name']}와 대화 중")
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])
            
        if prompt := st.chat_input("메시지 입력..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            # Gemini AI 응답 생성
            model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=cp['instruction'])
            response = model.generate_content(prompt)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()

# [탭 3: 이미지 게시판]
with tabs[2]:
    with st.expander("📸 사진 올리기 (가입 없이 가능)"):
        f = st.file_uploader("사진", type=['jpg','png'])
        d = st.text_input("사진 설명")
        if st.button("게시"):
            if f:
                fn = f"img_{uuid.uuid4()}.png"
                supabase.storage.from_("images").upload(fn, f.read())
                url = supabase.storage.from_("images").get_public_url(fn)
                u_id = st.session_state.user.id if st.session_state.user else "00000000-0000-0000-0000-000000000000"
                supabase.table("posts").insert({"user_id": u_id, "img_url": url, "description": d}).execute()
                st.rerun()
    
    for p in supabase.table("posts").select("*").order("created_at", desc=True).execute().data:
        st.image(p['img_url'], caption=p['description'], width=400)

# [탭 4: 커뮤니티 댓글]
with tabs[3]:
    with st.form("c_form", clear_on_submit=True):
        txt = st.text_area("익명으로 자유롭게 글을 남기세요")
        if st.form_submit_button("등록"):
            name = st.session_state.user.email if st.session_state.user else "Guest(익명)"
            supabase.table("comments").insert({"user_email": name, "content": txt}).execute()
            st.rerun()
    
    for c in supabase.table("comments").select("*").order("created_at", desc=True).execute().data:
        st.write(f"**{c['user_email']}**: {c['content']}")
        st.divider()

# [탭 5: 캐릭터 제작]
with tabs[4]:
    st.header("🛠️ 나만의 캐릭터 만들기")
    with st.form("make_char"):
        n = st.text_input("캐릭터 이름")
        d = st.text_input("소개 (예: 까칠한 고양이)")
        i = st.text_area("행동 지침 (AI가 어떻게 행동할지 구체적으로)")
        img = st.file_uploader("대표 이미지", type=['jpg','png'])
        comm = st.text_area("제작자의 코멘트")
        
        if st.form_submit_button("만들기"):
            img_url = None
            if img:
                if_n = f"char_{uuid.uuid4()}.png"
                supabase.storage.from_("images").upload(if_n, img.read())
                img_url = supabase.storage.from_("images").get_public_url(if_n)
            
            creator = st.session_state.user.email if st.session_state.user else "Guest"
            supabase.table("sai_characters").insert({
                "name": n, "description": d, "instruction": i,
                "image_url": img_url, "creator_comment": f"{creator}: {comm}"
            }).execute()
            st.success("새 캐릭터가 탄생했습니다!")