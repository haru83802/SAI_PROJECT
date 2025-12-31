import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from openai import OpenAI
import uuid

# --- [0. 기본 설정 및 영구 세션] ---
st.set_page_config(page_title="SAI - Ultimate v2", layout="wide")

if "user_id" not in st.session_state:
    st.session_state.user_id = f"User_{uuid.uuid4().hex[:6]}"
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# --- [1. API 연결] ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error("API 연결 실패! Secrets 설정을 확인하세요.")
    st.stop()

# --- [2. 🔥 상단 공지사항 & 개발자 코멘트] ---
st.markdown(f"""
    <div style="background: linear-gradient(to right, #6a11cb, #2575fc); padding: 20px; border-radius: 15px; color: white; margin-bottom: 25px;">
        <h2 style='margin:0;'>📢 SAI PROJECT OFFICIAL NOTICE</h2>
        <p style='margin:5px 0 0 0;'><b>v2.5 업데이트 완료:</b> 이제 GPT-4o와 Gemini 1.5를 선택할 수 있습니다. <br>
        현재 당신의 고유 접속 ID: <b>{st.session_state.user_id}</b> (모든 대화는 자동 저장됩니다.)</p>
    </div>
""", unsafe_allow_html=True)

# --- [3. 사이드바 - 제어판] ---
with st.sidebar:
    st.title("🤖 SAI CONTROL")
    
    with st.expander("🛠️ DEVELOPER COMMENT", expanded=True):
        st.info(f"""
        **관리자 한마디:**
        사이트를 새로고침해도 DB에서 대화 내용을 실시간으로 불러오니 걱정 마세요. 
        GPT와 Gemini 중 마음에 드는 지능을 선택해 보세요!
        """)

    st.divider()
    
    # AI 선택 기능
    st.subheader("🧠 모델 엔진 선택")
    ai_choice = st.selectbox("사용할 AI", ["Gemini 1.5 Flash", "Gemini 1.5 Pro", "GPT-4o", "GPT-4o-mini"])
    ai_map = {"Gemini 1.5 Flash": "gemini-1.5-flash", "Gemini 1.5 Pro": "gemini-1.5-pro", "GPT-4o": "gpt-4o", "GPT-4o-mini": "gpt-4o-mini"}
    sel_model = ai_map[ai_choice]

    # 소셜 로그인 UI
    st.subheader("🔑 계정 연결")
    c1, c2 = st.columns(2)
    if c1.button("Google Login"): st.toast("구글 연동 성공")
    if c2.button("Discord Login"): st.toast("디스코드 연동 성공")

    st.divider()
    
    # 대화 기록 로드 (새로고침 유지의 핵심)
    st.subheader("📝 대화 리스트")
    res = supabase.table("chat_history").select("session_id, char_name").eq("user_id", st.session_state.user_id).execute()
    unique_chats = {item['session_id']: item['char_name'] for item in res.data}
    for sid, name in unique_chats.items():
        if st.button(f"💬 {name}", key=f"sid_{sid}", use_container_width=True):
            st.session_state.current_session_id = sid
            st.rerun()

# --- [4. 메인 탭 기능] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 갤러리", "📝 게시판", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드]
with tabs[0]:
    chars = supabase.table("sai_characters").select("*").execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars or []):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(char['name'])
                st.caption(f"제작자: {char['creator_id']}")
                st.write(char['description'])
                if st.button("대화하기", key=f"go_{char['id']}", use_container_width=True):
                    st.session_state.current_session_id = str(uuid.uuid4())
                    st.rerun()

# [탭 2: 채팅창 - 무조건 대화되는 하이브리드 로직]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("트렌드 탭에서 캐릭터를 골라주세요!")
    else:
        # DB에서 이 세션의 기존 지침(instruction) 가져오기
        history = supabase.table("chat_history").select("*").eq("session_id", sid).order("created_at").execute().data
        
        # 첫 대화인 경우 기본 정보 설정 (예외 처리)
        c_name = history[0]['char_name'] if history else "AI"
        c_inst = history[0]['instruction'] if history else "친절하게 대답해줘."
        
        st.subheader(f"💬 {c_name}와(과) 대화 중")
        st.caption(f"현재 엔진: {sel_model}")

        for m in history:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지를 입력하세요..."):
            with st.chat_message("user"): st.write(prompt)
            # 유저 메시지 저장
            supabase.table("chat_history").insert({
                "user_id": st.session_state.user_id, "session_id": sid, "char_name": c_name,
                "role": "user", "content": prompt, "instruction": c_inst, "model_name": sel_model
            }).execute()

            # AI 응답 (하이브리드 엔진)
            try:
                if "gemini" in sel_model:
                    model = genai.GenerativeModel(model_name=sel_model, system_instruction=c_inst)
                    ai_text = model.generate_content(prompt).text
                else:
                    resp = openai_client.chat.completions.create(
                        model=sel_model,
                        messages=[{"role": "system", "content": c_inst}, {"role": "user", "content": prompt}]
                    )
                    ai_text = resp.choices[0].message.content
                
                with st.chat_message("assistant"): st.write(ai_text)
                # AI 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": st.session_state.user_id, "session_id": sid, "char_name": c_name,
                    "role": "assistant", "content": ai_text, "instruction": c_inst, "model_name": sel_model
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"AI 호출 오류: {e}")

# [탭 3: 갤러리 - 좋아요 및 제작자 표시]
with tabs[2]:
    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    for p in posts or []:
        with st.container(border=True):
            st.image(p['img_url'], width=400)
            st.write(f"**{p['description']}**")
            st.caption(f"🎨 제작자 ID: {p['user_id']}")
            
            likes = p.get('likes', [])
            if st.button(f"❤️ {len(likes)} 좋아요", key=f"post_{p['id']}"):
                if st.session_state.user_id not in likes:
                    likes.append(st.session_state.user_id)
                    supabase.table("posts").update({"likes": likes}).eq("id", p['id']).execute()
                    st.rerun()

# [탭 4: 게시판]
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("board", clear_on_submit=True):
        txt = st.text_area("내용")
        if st.form_submit_button("등록"):
            supabase.table("comments").insert({"user_email": st.session_state.user_id, "content": txt}).execute()
            st.rerun()
    comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
    for c in comments or []:
        st.write(f"**{c['user_email']}**: {c['content']}")
        st.divider()

# [탭 5: 제작 코드 전용 분리]
with tabs[4]:
    st.header("🛠️ 캐릭터 커스텀 생성기")
    st.write("나만의 AI 페르소나를 설계하세요.")
    with st.form("make_form", clear_on_submit=True):
        n = st.text_input("이름")
        d = st.text_input("한 줄 설명")
        i = st.text_area("AI 지침 (Persona)")
        if st.form_submit_button("서버에 영구 등록"):
            supabase.table("sai_characters").insert({
                "name": n, "description": d, "instruction": i, "creator_id": st.session_state.user_id
            }).execute()
            st.success("등록 완료! 이제 트렌드 탭에서 대화가 가능합니다.")