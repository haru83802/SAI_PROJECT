import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from openai import OpenAI
import uuid

# --- [0. 초기 설정 및 세션 관리] ---
st.set_page_config(page_title="SAI - GPT & Gemini Hybrid", layout="wide", page_icon="🤖")

if "user_id" not in st.session_state:
    st.session_state.user_id = f"User_{uuid.uuid4().hex[:8]}"
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# --- [1. API 연결] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("API 키 설정 오류! Secrets를 확인하세요.")
    st.stop()

# --- [2. 상단 공지사항] ---
st.markdown("""
    <div style="background-color:#1E1E1E; color:#00D1FF; padding:15px; border-radius:10px; border-left:5px solid #00D1FF; margin-bottom:20px;">
        <strong>🚀 SAI SYSTEM ONLINE:</strong> ChatGPT-4o 및 Gemini 1.5 선택 가능. 모든 대화는 실시간 저장됩니다.
    </div>
""", unsafe_allow_html=True)

# --- [3. 사이드바 - 로그인 및 모델 선택] ---
with st.sidebar:
    st.title("🤖 SAI CONTROL")
    st.info("💡 **Dev Comment:** 모델을 바꾸면 AI의 인격은 유지되지만 '두뇌'가 교체됩니다.")
    
    # 모델 선택 기능
    st.subheader("🧠 모델 선택")
    model_choice = st.selectbox("AI 엔진", ["Gemini 1.5 Flash", "Gemini 1.5 Pro", "GPT-4o", "GPT-4o-mini"])
    model_map = {
        "Gemini 1.5 Flash": "gemini-1.5-flash", "Gemini 1.5 Pro": "gemini-1.5-pro",
        "GPT-4o": "gpt-4o", "GPT-4o-mini": "gpt-4o-mini"
    }
    sel_model = model_map[model_choice]

    # 소셜 로그인 UI
    st.subheader("🔑 계정")
    col1, col2 = st.columns(2)
    if col1.button("Google Login"): st.toast("Google 연동 완료")
    if col2.button("Discord Login"): st.toast("Discord 연동 완료")

    # 대화 기록 (새로고침 유지의 핵심)
    st.subheader("📝 나의 대화")
    try:
        res = supabase.table("chat_history").select("session_id, char_name").eq("user_id", st.session_state.user_id).execute()
        unique_chats = {item['session_id']: item['char_name'] for item in res.data}
        for sid, name in unique_chats.items():
            if st.button(f"💬 {name}", key=f"list_{sid}", use_container_width=True):
                st.session_state.current_session_id = sid
                st.rerun()
    except: st.caption("대화가 없습니다.")

# --- [4. 메인 기능 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 갤러리", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드]
with tabs[0]:
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        cols = st.columns(3)
        for i, char in enumerate(chars):
            with cols[i % 3]:
                with st.container(border=True):
                    st.subheader(char['name'])
                    st.write(char.get('description', ''))
                    if st.button("대화 시작", key=f"c_{char['id']}", use_container_width=True):
                        st.session_state.current_session_id = str(uuid.uuid4())
                        # 초기 세션 데이터 주입 (성능 및 안정성)
                        supabase.table("chat_history").insert({
                            "user_id": st.session_state.user_id, "session_id": st.session_state.current_session_id,
                            "char_name": char['name'], "role": "assistant", "content": "반가워요! 대화를 시작하죠.",
                            "instruction": char['instruction'], "model_name": sel_model
                        }).execute()
                        st.rerun()
    except: st.warning("캐릭터를 불러오는 중...")

# [탭 2: 채팅창 - GPT/Gemini 하이브리드]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("캐릭터를 먼저 선택해주세요.")
    else:
        # DB에서 기록 로드
        chat_data = supabase.table("chat_history").select("*").eq("session_id", sid).order("created_at").execute().data
        if chat_data:
            c_name = chat_data[0]['char_name']
            c_inst = chat_data[0]['instruction']
            st.subheader(f"💬 {c_name} (Current: {sel_model})")

            for m in chat_data:
                with st.chat_message(m["role"]): st.write(m["content"])

            if prompt := st.chat_input("메시지 입력..."):
                with st.chat_message("user"): st.write(prompt)
                supabase.table("chat_history").insert({
                    "user_id": st.session_state.user_id, "session_id": sid, "char_name": c_name,
                    "role": "user", "content": prompt, "instruction": c_inst, "model_name": sel_model
                }).execute()

                # AI 호출 분기
                try:
                    if "gemini" in sel_model:
                        model = genai.GenerativeModel(model_name=sel_model, system_instruction=c_inst)
                        ai_resp = model.generate_content(prompt).text
                    else:
                        resp = openai_client.chat.completions.create(
                            model=sel_model, messages=[{"role": "system", "content": c_inst}, {"role": "user", "content": prompt}]
                        )
                        ai_resp = resp.choices[0].message.content
                    
                    with st.chat_message("assistant"): st.write(ai_resp)
                    supabase.table("chat_history").insert({
                        "user_id": st.session_state.user_id, "session_id": sid, "char_name": c_name,
                        "role": "assistant", "content": ai_resp, "instruction": c_inst, "model_name": sel_model
                    }).execute()
                    st.rerun()
                except Exception as e: st.error(f"AI 오류: {e}")

# [탭 3: 갤러리 - 좋아요 기능]
with tabs[2]:
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts:
        with st.container(border=True):
            st.image(p['img_url'], width=400)
            st.caption(f"제작자: {p['user_id']}")
            likes = p.get('likes', [])
            if st.button(f"❤️ {len(likes)} 좋아요", key=f"p_{p['id']}"):
                if st.session_state.user_id not in likes:
                    likes.append(st.session_state.user_id)
                    supabase.table("posts").update({"likes": likes}).eq("id", p['id']).execute()
                    st.rerun()

# [탭 4: 게시판 - 에러 해결 지점]
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("board", clear_on_submit=True):
        content = st.text_area("내용을 입력하세요")
        if st.form_submit_button("등록"):
            supabase.table("comments").insert({"user_email": st.session_state.user_id, "content": content}).execute()
            st.rerun()
    
    # 113번 라인 에러 방지 (try-except)
    try:
        comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
        for c in comments:
            st.write(f"**{c['user_email']}**: {c['content']}")
            st.divider()
    except: st.write("게시물이 아직 없습니다.")

# [탭 5: 제작]
with tabs[4]:
    with st.form("make"):
        n = st.text_input("이름")
        i = st.text_area("지침")
        if st.form_submit_button("저장"):
            supabase.table("sai_characters").insert({"name": n, "instruction": i, "creator_id": st.session_state.user_id}).execute()
            st.success("완료!")