import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from security import sai_guard
import uuid

# --- [0. 초기화] ---
if "user" not in st.session_state: st.session_state.user = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- [1. 설정 및 연결] ---
st.set_page_config(page_title="SAI - 통합 시스템", layout="wide", page_icon="🤖")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"설정 오류: Secrets를 확인하세요. ({e})")
    st.stop()

# --- [2. 유저 식별 및 데이터 로드] ---
u_id = st.session_state.user.id if st.session_state.user else f"Guest_{sai_guard.get_remote_ip()}"

if not st.session_state.chat_sessions:
    try:
        res = supabase.table("chat_history").select("session_id, char_name, instruction").eq("user_id", u_id).execute()
        temp = {}
        for item in res.data:
            sid = str(item['session_id'])
            if sid not in temp:
                temp[sid] = {"char_name": item['char_name'], "instruction": item['instruction'], "messages": []}
        st.session_state.chat_sessions = temp
    except: pass

# --- [3. 사이드바: 모델 설정 및 대화 목록] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    st.subheader("⚙️ AI 모델 엔진")
    # 404 에러 방지를 위한 표준 명칭
    selected_model_name = st.selectbox("엔진 선택", ["gemini-1.5-flash", "gemini-1.5-pro"])
    
    st.divider()
    st.subheader("📝 나의 대화")
    for s_id, s_data in st.session_state.chat_sessions.items():
        if st.button(f"💬 {s_data['char_name']}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()
    if st.button("➕ 새 캐릭터와 시작", use_container_width=True):
        st.session_state.current_session_id = None
        st.rerun()

# --- [4. 메인 콘텐츠 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드 - 캐릭터 선택]
with tabs[0]:
    st.subheader("대화하고 싶은 AI를 선택하세요")
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        cols = st.columns(3)
        for i, char in enumerate(chars or []):
            with cols[i % 3]:
                if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                st.info(f"**{char['name']}**")
                if st.button("대화 시작", key=f"char_{char['id']}"):
                    new_id = str(uuid.uuid4())
                    st.session_state.chat_sessions[new_id] = {
                        "char_name": char['name'], "instruction": char['instruction'], "messages": []
                    }
                    st.session_state.current_session_id = new_id
                    st.rerun()
    except: st.warning("캐릭터 목록을 불러올 수 없습니다.")

# [탭 2: 채팅창 - 핵심 해결 로직]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.warning("먼저 캐릭터를 골라주세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.subheader(f"💬 {chat['char_name']} ({selected_model_name})")

        # 실시간 메시지 로드
        try:
            res = supabase.table("chat_history").select("role, content").eq("session_id", sid).order("created_at").execute()
            chat["messages"] = res.data
        except: pass

        for m in chat["messages"]:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지 입력..."):
            with st.chat_message("user"): st.write(prompt)
            try:
                # 1. 유저 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "user", "content": prompt, "instruction": chat['instruction']
                }).execute()
                
                # 2. AI 호출 (404 방지 강제 경로 설정)
                ai_text = ""
                # 라이브러리 버전에 따라 'models/'가 필수일 수 있음
                model_id = f"models/{selected_model_name}"
                
                model = genai.GenerativeModel(model_name=model_id, system_instruction=chat['instruction'])
                response = model.generate_content(prompt)
                ai_text = response.text
                
                # 3. AI 응답 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "assistant", "content": ai_text, "instruction": chat['instruction']
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ 연결 오류: {e}")
                st.info("API 키 권한이나 할당량을 확인하세요.")

# [탭 3: 이미지 갤러리]
with tabs[2]:
    st.header("📸 이미지 갤러리")
    with st.expander("내 이미지 공유"):
        img_f = st.file_uploader("사진 선택", type=['jpg', 'png'])
        img_d = st.text_input("설명")
        if st.button("업로드") and img_f:
            try:
                fn = f"{uuid.uuid4()}.png"
                supabase.storage.from_("images").upload(fn, img_f.read())
                url = supabase.storage.from_("images").get_public_url(fn)
                supabase.table("posts").insert({"user_id": u_id, "img_url": url, "description": img_d}).execute()
                st.rerun()
            except: st.error("Storage 버킷 'images'가 공개 상태인지 확인하세요.")
    
    try:
        posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
        cols = st.columns(3)
        for idx, p in enumerate(posts or []):
            with cols[idx % 3]:
                st.image(p['img_url'], use_container_width=True)
                st.caption(p['description'])
    except: st.write("공유된 이미지가 없습니다.")

# [탭 4: 커뮤니티]
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("comm_form", clear_on_submit=True):
        txt = st.text_area("내용을 입력하세요")
        if st.form_submit_button("등록"):
            if txt.strip():
                try:
                    author = st.session_state.user.email if st.session_state.user else "익명"
                    supabase.table("comments").insert({"user_email": author, "content": txt}).execute()
                    st.rerun()
                except: st.error("게시판 저장 실패")
    
    try:
        comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
        for c in comments or []:
            st.write(f"**{c['user_email']}**: {c['content']}")
            st.divider()
    except: st.write("글이 없습니다.")

# [탭 5: 캐릭터 제작]
with tabs[4]:
    st.header("🛠️ 캐릭터 제작")
    with st.form("make_form"):
        name = st.text_input("이름")
        desc = st.text_input("한 줄 소개")
        inst = st.text_area("성격 지침")
        if st.form_submit_button("제작"):
            if name and inst:
                try:
                    supabase.table("sai_characters").insert({"name": name, "description": desc, "instruction": inst}).execute()
                    st.success(f"{name} 캐릭터 제작 완료!")
                except: st.error("DB 권한 오류 (RLS를 해제하세요)")
