import streamlit as st
from supabase import create_client, Client
from google import genai
from security import sai_guard
import uuid

# --- [0. 초기화] ---
if "user" not in st.session_state: st.session_state.user = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- [1. 설정 및 연결] ---
st.set_page_config(page_title="SAI - 통합 챗봇 시스템", layout="wide", page_icon="🤖")

try:
    # Supabase 및 Google AI 클라이언트 연결
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"연결 설정 오류: {e}")
    st.stop()

# --- [2. 사용자 데이터 로드] ---
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

# --- [3. 사이드바: 모델 및 세션 목록] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    st.subheader("⚙️ 모델 설정")
    # 최신 모델 리스트 제공
    selected_model = st.selectbox(
        "엔진 선택", 
        ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
    )
    st.caption("※ 429 에러 발생 시 1.5-flash를 권장합니다.")
    
    st.divider()
    st.subheader("📝 내 대화 목록")
    for s_id, s_data in st.session_state.chat_sessions.items():
        if st.button(f"💬 {s_data['char_name']}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()
    if st.button("➕ 새 대화 시작", use_container_width=True):
        st.session_state.current_session_id = None
        st.rerun()

# --- [4. 메인 콘텐츠] ---
tabs = st.tabs(["🔥 트렌드", "💬 SAI 챗봇", "📸 갤러리", "📝 커뮤니티", "🛠️ 제작소"])

# [탭 1: 캐릭터 선택]
with tabs[0]:
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
    except: st.warning("캐릭터를 불러올 수 없습니다.")

# [탭 2: SAI 챗봇 메인]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("👈 사이드바에서 대화를 선택하거나 트렌드 탭에서 캐릭터를 골라주세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.subheader(f"💬 {chat['char_name']} (엔진: {selected_model})")

        # 실시간 메시지 로드
        try:
            res = supabase.table("chat_history").select("role, content").eq("session_id", sid).order("created_at").execute()
            chat["messages"] = res.data
        except: pass

        for m in chat["messages"]:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지를 입력하세요..."):
            with st.chat_message("user"): st.write(prompt)
            try:
                # 1. 유저 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "user", "content": prompt, "instruction": chat['instruction']
                }).execute()
                
                # 2. AI 호출 (404/429 방어 로직)
                try:
                    response = client.models.generate_content(
                        model=selected_model,
                        contents=prompt,
                        config={'system_instruction': chat['instruction'], 'temperature': 0.7}
                    )
                    ai_text = response.text
                except Exception as api_err:
                    if "429" in str(api_err):
                        st.warning("⚠️ 할당량 초과! gemini-1.5-flash로 자동 전환하여 응답합니다.")
                        fallback = client.models.generate_content(
                            model="gemini-1.5-flash",
                            contents=prompt,
                            config={'system_instruction': chat['instruction']}
                        )
                        ai_text = fallback.text
                    else: raise api_err

                # 3. AI 응답 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "assistant", "content": ai_text, "instruction": chat['instruction']
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")

# [탭 3: 갤러리]
with tabs[2]:
    st.header("📸 사진 갤러리")
    with st.expander("내 사진 공유하기"):
        img_f = st.file_uploader("사진 선택", type=['jpg', 'png'])
        img_d = st.text_input("설명")
        if st.button("업로드") and img_f:
            fn = f"{uuid.uuid4()}.png"
            supabase.storage.from_("images").upload(fn, img_f.read())
            url = supabase.storage.from_("images").get_public_url(fn)
            supabase.table("posts").insert({"user_id": u_id, "img_url": url, "description": img_d}).execute()
            st.rerun()
    
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    cols = st.columns(3)
    for idx, p in enumerate(posts or []):
        with cols[idx%3]:
            st.image(p['img_url'], use_container_width=True)
            st.caption(p.get('description', ''))

# [탭 4: 커뮤니티 게시판]
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("comm", clear_on_submit=True):
        t = st.text_area("글 내용 입력")
        if st.form_submit_button("등록"):
            if t.strip():
                supabase.table("comments").insert({"user_email": "User", "content": t}).execute()
                st.rerun()
    
    comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
    for c in comments or []:
        st.write(f"**유저**: {c['content']}")
        st.divider()

# [탭 5: 캐릭터 제작소]
with tabs[4]:
    st.header("🛠️ 캐릭터 제작")
    with st.form("make"):
        n = st.text_input("캐릭터 이름")
        i = st.text_area("AI 지침 (성격 등)")
        if st.form_submit_button("생성"):
            if n and i:
                supabase.table("sai_characters").insert({"name": n, "instruction": i}).execute()
                st.success(f"{n} 캐릭터 생성 완료!
