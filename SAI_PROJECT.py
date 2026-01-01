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
st.set_page_config(page_title="SAI - 우리 사이 AI", layout="wide", page_icon="🤖")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("Secrets 설정 오류! (URL, KEY, GEMINI_API_KEY 확인)")
    st.stop()

# --- [2. 사용자 식별 및 데이터 로드] ---
u_id = st.session_state.user.id if st.session_state.user else f"Guest_{sai_guard.get_remote_ip()}"

# 앱 시작 시 DB에서 해당 유저의 대화 세션 목록을 영구 로드
if not st.session_state.chat_sessions:
    try:
        res = supabase.table("chat_history").select("session_id, char_name, instruction").eq("user_id", u_id).execute()
        temp_sessions = {}
        for item in res.data:
            sid = str(item['session_id'])
            if sid not in temp_sessions:
                temp_sessions[sid] = {
                    "char_name": item['char_name'],
                    "instruction": item['instruction'],
                    "messages": [] 
                }
        st.session_state.chat_sessions = temp_sessions
    except:
        pass

# --- [3. 사이드바: 모델 선택 및 대화 목록] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    
    st.subheader("⚙️ AI 모델 엔진")
    selected_model = st.selectbox(
        "사용할 AI 버전을 선택하세요",
        ["gemini-1.5-flash", "gemini-1.5-pro"],
        help="Flash는 빠르고 Pro는 더 똑똑하지만 느릴 수 있습니다."
    )
    
    st.divider()
    
    st.subheader("📝 나의 대화 목록")
    if not st.session_state.chat_sessions:
        st.caption("새로운 대화를 시작해 보세요.")
    else:
        for s_id, s_data in st.session_state.chat_sessions.items():
            if st.button(f"💬 {s_data['char_name']}", key=f"btn_{s_id}", use_container_width=True):
                st.session_state.current_session_id = s_id
                st.rerun()

    if st.button("➕ 새 캐릭터와 대화하기", use_container_width=True):
        st.session_state.current_session_id = None
        st.rerun()

# --- [4. 메인 콘텐츠 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 이미지", "📝 커뮤니티", "🛠️ 캐릭터 제작"])

# [탭 1: 트렌드 - 캐릭터 선택]
with tabs[0]:
    st.subheader("AI 캐릭터 선택")
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        cols = st.columns(3)
        for i, char in enumerate(chars):
            with cols[i % 3]:
                if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                st.info(f"**{char['name']}**")
                st.caption(char.get('description', ''))
                if st.button("대화 시작", key=f"sel_{char['id']}"):
                    new_id = str(uuid.uuid4())
                    st.session_state.chat_sessions[new_id] = {
                        "char_name": char['name'], "instruction": char['instruction'], "messages": []
                    }
                    st.session_state.current_session_id = new_id
                    st.rerun()
    except:
        st.warning("캐릭터 목록을 불러올 수 없습니다.")

# [탭 2: 채팅창]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.warning("사이드바에서 대화를 선택하거나 '트렌드'에서 새 대화를 시작하세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.subheader(f"💬 {chat['char_name']} (엔진: {selected_model})")

        if not chat["messages"]:
            try:
                res = supabase.table("chat_history").select("*").eq("session_id", sid).order("created_at").execute()
                chat["messages"] = [{"role": r["role"], "content": r["content"]} for r in res.data]
            except: pass

        for m in chat["messages"]:
            with st.chat_message(m["role"]): st.write(m["content"])

        if prompt := st.chat_input("메시지를 입력하세요..."):
            chat["messages"].append({"role": "user", "content": prompt})
            try:
                # 1. 유저 메시지 서버 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "user", "content": prompt, "instruction": chat['instruction']
                }).execute()
                
                # 2. AI 호출
                try:
                    model = genai.GenerativeModel(model_name=selected_model, system_instruction=chat['instruction'])
                    response = model.generate_content(prompt)
                except:
                    model = genai.GenerativeModel(model_name=f"models/{selected_model}", system_instruction=chat['instruction'])
                    response = model.generate_content(prompt)
                
                ai_text = response.text
                
                # 3. AI 답변 서버 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "assistant", "content": ai_text, "instruction": chat['instruction']
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ 오류 발생: {e}")

# [탭 3: 이미지 갤러리]
with tabs[2]:
    st.header("📸 이미지 갤러리")
    with st.expander("내 이미지 공유하기"):
        img_file = st.file_uploader("사진 선택", type=['jpg', 'png', 'jpeg'])
        img_desc = st.text_input("이미지 설명")
        if st.button("업로드") and img_file:
            fname = f"post_{uuid.uuid4()}.png"
            supabase.storage.from_("images").upload(fname, img_file.read())
            url = supabase.storage.from_("images").get_public_url(fname)
            supabase.table("posts").insert({"user_id": u_id, "img_url": url, "description": img_desc}).execute()
            st.success("업로드 완료!")
            st.rerun()

    posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
    cols = st.columns(3)
    for idx, p in enumerate(posts):
        with cols[idx % 3]:
            st.image(p['img_url'], use_container_width=True)
            st.caption(p['description'])

# [탭 4: 커뮤니티]
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("comment_form", clear_on_submit=True):
        comment_txt = st.text_area("SAI 유저들과 대화해보세요.")
        if st.form_submit_button("등록"):
            author = st.session_state.user.email if st.session_state.user else "익명의 유저"
            supabase.table("comments").insert({"user_email": author, "content": comment_txt}).execute()
            st.rerun()
    
    comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
    for c in comments:
        st.write(f"**{c['user_email']}** : {c['content']}")
        st.caption(f"작성일: {c['created_at'][:10]}")
        st.divider()

# [탭 5: 캐릭터 제작]
with tabs[4]:
    st.header("🛠️ 나만의 AI 캐릭터 만들기")
    with st.form("create_char"):
        c_name = st.text_input("캐릭터 이름 (예: 까칠한 고양이)")
        c_desc = st.text_input("한 줄 소개")
        c_inst = st.text_area("AI 지침 (예: 너는 고양이야. 모든 말 끝에 '냥'을 붙여줘.)")
        c_img = st.file_uploader("캐릭터 프로필 이미지", type=['jpg', 'png'])
        
        if st.form_submit_button("캐릭터 등록"):
            img_url = ""
            if c_img:
                if_name = f"char_{uuid.uuid4()}.png"
                supabase.storage.from_("images").upload(if_name, c_img.read())
                img_url = supabase.storage.from_("images").get_public_url(if_name)
            
            supabase.table("sai_characters").insert({
                "name": c_name, 
                "description": c_desc, 
                "instruction": c_inst, 
                "image_url": img_url
            }).execute()
            st.success(f"{c_name} 캐릭터가 생성되었습니다! '트렌드' 탭에서 확인하세요.")