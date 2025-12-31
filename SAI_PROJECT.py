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
st.set_page_config(page_title="SAI - 최종 통합본", layout="wide", page_icon="🤖")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("Secrets 설정 오류! (URL, KEY, GEMINI_API_KEY를 확인하세요)")
    st.stop()

# --- [2. 사용자 식별 및 로드] ---
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

# --- [3. 사이드바] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    st.subheader("📝 대화 목록")
    for s_id, s_data in st.session_state.chat_sessions.items():
        if st.button(f"💬 {s_data['char_name']}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()
    if st.button("➕ 새 대화 시작", use_container_width=True):
        st.session_state.current_session_id = None
        st.rerun()

# --- [4. 메인 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드]
with tabs[0]:
    st.subheader("캐릭터 선택")
    chars = supabase.table("sai_characters").select("*").execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars):
        with cols[i % 3]:
            if char.get('image_url'): st.image(char['image_url'])
            st.info(f"**{char['name']}**")
            if st.button("대화 시작", key=f"char_{char['id']}"):
                new_id = str(uuid.uuid4())
                st.session_state.chat_sessions[new_id] = {
                    "char_name": char['name'], "instruction": char['instruction'], "messages": []
                }
                st.session_state.current_session_id = new_id
                st.rerun()

# [탭 2: 채팅창 - 영구 저장 및 404 에러 방지]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.warning("먼저 캐릭터를 골라주세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.subheader(f"💬 {chat['char_name']}")

        if not chat["messages"]:
            res = supabase.table("chat_history").select("*").eq("session_id", str(sid)).order("created_at").execute()
            chat["messages"] = [{"role": r["role"], "content": r["content"]} for r in res.data]

        for m in chat["messages"]:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지 입력..."):
            chat["messages"].append({"role": "user", "content": prompt})
            
            try:
                # 1. 유저 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "user", "content": prompt, "instruction": chat['instruction']
                }).execute()
                
                # 2. AI 응답 생성 (404 방지용 Fallback 로직)
                ai_text = ""
                # 시도할 모델 이름 리스트
                model_names = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
                
                success = False
                for m_name in model_names:
                    try:
                        model = genai.GenerativeModel(model_name=m_name, system_instruction=chat['instruction'])
                        response = model.generate_content(prompt)
                        ai_text = response.text
                        success = True
                        break
                    except: continue
                
                if not success:
                    raise Exception("모든 Gemini 모델 호출에 실패했습니다.")

                # 3. AI 답변 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "assistant", "content": ai_text, "instruction": chat['instruction']
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"서버 오류: {e}")

# [탭 3, 4, 5는 이전과 동일]
# 이미지 게시판
with tabs[2]:
    st.header("📸 이미지 갤러리")
    for p in supabase.table("posts").select("*").order("created_at", desc=True).execute().data:
        st.image(p['img_url'], caption=p['description'], width=300)

# 커뮤니티
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("comm", clear_on_submit=True):
        txt = st.text_area("내용")
        if st.form_submit_button("등록"):
            author = st.session_state.user.email if st.session_state.user else "Guest"
            supabase.table("comments").insert({"user_email": author, "content": txt}).execute()
            st.rerun()
    for c in supabase.table("comments").select("*").order("created_at", desc=True).execute().data:
        st.write(f"**{c['user_email']}**: {c['content']}")

# 캐릭터 제작
with tabs[4]:
    st.header("🛠️ 캐릭터 제작")
    with st.form("make"):
        name = st.text_input("이름")
        inst = st.text_area("지침")
        if st.form_submit_button("만들기"):
            supabase.table("sai_characters").insert({"name": name, "instruction": inst}).execute()
            st.success("완료!")