import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from security import sai_guard
import uuid # 고유 파일명 생성용

# --- [0. 접속 차단 보안] ---
if sai_guard.is_banned():
    st.error("🚫 보안 위협으로 인해 차단된 IP입니다.")
    st.stop()

# --- [1. 기본 설정] ---
st.set_page_config(page_title="SAI - 이미지 & 커뮤니티", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("설정 오류")
    st.stop()

# --- [2. 세션 상태] ---
if "user" not in st.session_state: st.session_state.user = None

# --- [3. 사이드바 (로그인)] ---
with st.sidebar:
    st.title("👤 SAI 센터")
    if st.session_state.user is None:
        email = st.text_input("이메일")
        pw = st.text_input("비밀번호", type="password")
        if st.button("로그인"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("로그인 실패")
    else:
        st.success(f"{st.session_state.user.email}님")
        if st.button("로그아웃"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

# --- [4. 메인 기능: 탭 구성] ---
tabs = st.tabs(["💬 AI 채팅", "📸 이미지 게시판", "📝 자유 댓글"])

# --- [탭 1: AI 채팅 (기존 기능)] ---
with tabs[0]:
    st.header("AI 캐릭터와 대화")
    st.write("캐릭터를 선택하고 대화를 시작하세요.")

# --- [탭 2: 이미지 업로드 기능] ---
with tabs[1]:
    st.header("📸 이미지 공유")
    if st.session_state.user:
        with st.expander("이미지 올리기"):
            img_file = st.file_uploader("이미지 선택", type=['png', 'jpg', 'jpeg'])
            img_desc = st.text_input("설명")
            
            if st.button("업로드"):
                is_safe, msg = sai_guard.validate_image(img_file)
                if is_safe:
                    # 파일명 중복 방지 (UUID)
                    file_ext = img_file.name.split(".")[-1]
                    file_name = f"{uuid.uuid4()}.{file_ext}"
                    
                    # 1. Supabase Storage 업로드 (버킷 이름: 'images')
                    storage_res = supabase.storage.from_("images").upload(file_name, img_file.read())
                    
                    # 2. DB에 이미지 정보 저장
                    img_url = supabase.storage.from_("images").get_public_url(file_name)
                    supabase.table("posts").insert({
                        "user_id": st.session_state.user.id,
                        "img_url": img_url,
                        "description": sai_guard.sanitize_text(img_desc)
                    }).execute()
                    st.success("업로드 완료!")
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.warning("로그인 후 이용 가능합니다.")

    # 이미지 리스트 출력
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts:
        st.image(p['img_url'], caption=p['description'], width=300)
        st.divider()

# --- [탭 3: 자유 댓글 게시판] ---
with tabs[2]:
    st.header("📝 자유 댓글창")
    
    # 댓글 입력
    if st.session_state.user:
        with st.form("comment_form", clear_on_submit=True):
            comment_text = st.text_area("댓글을 남겨주세요")
            if st.form_submit_button("등록"):
                safe_comment = sai_guard.sanitize_text(comment_text)
                is_ok, error_msg = sai_guard.check_malicious(safe_comment)
                
                if is_ok:
                    supabase.table("comments").insert({
                        "user_email": st.session_state.user.email,
                        "content": safe_comment
                    }).execute()
                    st.success("댓글이 등록되었습니다.")
                    st.rerun()
                else:
                    st.error(error_msg)
    else:
        st.info("로그인하면 댓글을 남길 수 있습니다.")

    # 댓글 목록 보기
    comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
    for c in comments:
        st.write(f"**{c['user_email']}**: {c['content']}")
        st.caption(f"{c['created_at']}")
        st.divider()