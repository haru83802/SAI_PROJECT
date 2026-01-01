import streamlit as st
from supabase import create_client, Client
from google import genai 
from security import sai_guard
import uuid

# --- [0. 시스템 초기화] ---
if "user" not in st.session_state: st.session_state.user = None
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- [1. 설정 및 연결] ---
st.set_page_config(page_title="SAI - 시스템 안정화", layout="wide", page_icon="🤖")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"⚠️ 시스템 연결 실패: {e}")
    st.stop()

# --- [2. 데이터 로드] ---
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

# --- [3. 사이드바: 모델 설정] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    st.subheader("🚀 엔진 설정")
    
    # [수정됨] 429 에러 방지를 위해 'gemini-1.5-flash'를 제일 앞에 둠 (기본값)
    # 2.0이나 3.0은 API 키 권한이 생길 때까지 뒤로 미뤄둠
    selected_model = st.selectbox(
        "AI 모델 선택", 
        ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
    )
    
    if "1.5" in selected_model:
        st.success(f"✅ 안정적인 모델 사용 중: {selected_model}")
    else:
        st.warning("⚠️ 베타 모델은 할당량 초과(429)가 발생할 수 있습니다.")
    
    st.divider()
    st.subheader("📝 내 대화 목록")
    for s_id, s_data in st.session_state.chat_sessions.items():
        if st.button(f"💬 {s_data['char_name']}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()
            
    if st.button("➕ 새 캐릭터와 대화하기", use_container_width=True):
        st.session_state.current_session_id = None
        st.rerun()

# --- [4. 메인 콘텐츠] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "📸 갤러리", "📝 게시판", "🛠️ 제작소"])

# [탭 1: 캐릭터 선택]
with tabs[0]:
    st.header("인기 캐릭터")
    try:
        chars = supabase.table("sai_characters").select("*").execute().data
        cols = st.columns(3)
        for i, char in enumerate(chars or []):
            with cols[i % 3]:
                if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                st.subheader(char['name'])
                if st.button("대화 시작", key=f"start_{char['id']}"):
                    new_id = str(uuid.uuid4())
                    st.session_state.chat_sessions[new_id] = {
                        "char_name": char['name'], "instruction": char['instruction'], "messages": []
                    }
                    st.session_state.current_session_id = new_id
                    st.rerun()
    except: st.error("캐릭터 로딩 실패")

# [탭 2: 채팅창 - 안정화 로직]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("👈 사이드바에서 대화방을 선택하거나, [트렌드] 탭에서 캐릭터를 골라주세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.subheader(f"💬 {chat['char_name']}")

        # DB 메시지 로드
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
                
                # 2. AI 호출 (에러 핸들링 강화)
                try:
                    response = client.models.generate_content(
                        model=selected_model,
                        contents=prompt,
                        config={
                            'system_instruction': chat['instruction'],
                            'temperature': 0.7,
                        }
                    )
                    ai_text = response.text
                except Exception as api_error:
                    # 429 에러 발생 시 자동으로 1.5 Flash로 재시도하는 복구 로직
                    if "429" in str(api_error) or "RESOURCE_EXHAUSTED" in str(api_error):
                        st.warning("⚠️ 선택한 모델의 할당량이 초과되어 'gemini-1.5-flash'로 자동 전환합니다.")
                        fallback_response = client.models.generate_content(
                            model="gemini-1.5-flash",
                            contents=prompt,
                            config={'system_instruction': chat['instruction']}
                        )
                        ai_text = fallback_response.text
                    else:
                        raise api_error # 다른 에러는 그대로 던짐
                
                # 3. AI 응답 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "assistant", "content": ai_text, "instruction": chat['instruction']
                }).execute()
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ 전송 실패: {e}")
                st.info("잠시 후 다시 시도해 주세요.")

# [탭 3, 4, 5는 기능 유지]
with tabs[2]: # 갤러리
    with st.expander("📷 사진 업로드"):
        img_f = st.file_uploader("이미지", type=['jpg', 'png'])
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
        with cols[idx%3]: st.image(p['img_url']); st.caption(p.get('description'))

with tabs[3]: # 게시판
    with st.form("comm"):
        t = st.text_area("내용")
        if st.form_submit_button("등록") and t:
            supabase.table("comments").insert({"user_email": "User", "content": t}).execute()
            st.rerun()
    for c in supabase.table("comments").select("*").order("created_at", desc=True).execute().data or []:
        st.write(f"**User**: {c['content']}"); st.divider()

with tabs[4]: # 제작
    with st.form("make"):
        n=st.text_input("이름"); i=st.text_area("지침")
        if st.form_submit_button("제작") and n:
            supabase.table("sai_characters").insert({"name": n, "instruction": i}).execute()
            st.success("완료")
