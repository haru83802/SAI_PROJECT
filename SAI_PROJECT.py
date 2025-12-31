import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from security import sai_guard
import uuid

# --- [0. 시스템 초기화] ---
if "user" not in st.session_state: st.session_state.user = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- [1. 설정 및 연결] ---
st.set_page_config(page_title="SAI - 시스템 복구 완료", layout="wide", page_icon="🤖")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("Secrets 설정 오류!")
    st.stop()

# --- [2. 사용자 식별] ---
u_id = st.session_state.user.id if st.session_state.user else f"Guest_{sai_guard.get_remote_ip()}"

# 서버에서 내 대화 목록 불러오기 (최초 1회)
if not st.session_state.chat_sessions:
    try:
        res = supabase.table("chat_history").select("session_id, char_name, instruction").eq("user_id", u_id).execute()
        for item in res.data:
            sid = str(item['session_id']) # 안전하게 문자열 변환
            if sid not in st.session_state.chat_sessions:
                st.session_state.chat_sessions[sid] = {
                    "char_name": item['char_name'],
                    "instruction": item['instruction'],
                    "messages": []
                }
    except:
        pass

# --- [3. 사이드바: 목록] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    st.subheader("📝 대화 리스트")
    for s_id, s_data in st.session_state.chat_sessions.items():
        if st.button(f"💬 {s_data['char_name']}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()
    if st.button("➕ 새 대화", use_container_width=True):
        st.session_state.current_session_id = None
        st.rerun()

# --- [4. 메인 콘텐츠] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

with tabs[0]:
    st.subheader("캐릭터 선택")
    chars = supabase.table("sai_characters").select("*").execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars):
        with cols[i % 3]:
            if char.get('image_url'): st.image(char['image_url'])
            st.info(f"**{char['name']}**")
            if st.button("대화하기", key=f"char_{char['id']}"):
                new_id = str(uuid.uuid4()) # 새 세션 ID 생성
                st.session_state.chat_sessions[new_id] = {
                    "char_name": char['name'], "instruction": char['instruction'], "messages": []
                }
                st.session_state.current_session_id = new_id
                st.rerun()

with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.warning("먼저 대화할 캐릭터를 골라주세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.subheader(f"💬 {chat['char_name']}")

        # 과거 메시지 로드
        if not chat["messages"]:
            try:
                res = supabase.table("chat_history").select("*").eq("session_id", str(sid)).order("created_at").execute()
                chat["messages"] = [{"role": r["role"], "content": r["content"]} for r in res.data]
            except: pass

        for m in chat["messages"]:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지 입력..."):
            chat["messages"].append({"role": "user", "content": prompt})
            
            # DB 저장 및 AI 응답 처리 (에러 방지용 try-except)
            try:
                # 1. 유저 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), 
                    "session_id": str(sid), 
                    "char_name": chat['char_name'],
                    "role": "user", 
                    "content": prompt, 
                    "instruction": chat['instruction']
                }).execute()
                
                # 2. AI 응답 생성
                model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=chat['instruction'])
                response = model.generate_content(prompt)
                ai_text = response.text
                
                # 3. AI 답변 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), 
                    "session_id": str(sid), 
                    "char_name": chat['char_name'],
                    "role": "assistant", 
                    "content": ai_text, 
                    "instruction": chat['instruction']
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"서버 저장 중 오류: {e}")

# 이미지, 커뮤니티, 제작 탭은 이전 코드와 동일
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