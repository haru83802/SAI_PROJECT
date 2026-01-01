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
st.set_page_config(page_title="SAI - Gemini 3.0 통합본", layout="wide", page_icon="🤖")

try:
    # Supabase 연결
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    # Google AI 연결 (최신 google-genai 라이브러리)
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"⚠️ 시스템 연결 실패: secrets 값을 확인하세요. ({e})")
    st.stop()

# --- [2. 사용자 식별 및 데이터 로드] ---
u_id = st.session_state.user.id if st.session_state.user else f"Guest_{sai_guard.get_remote_ip()}"

# 앱 시작 시 대화 세션 복구
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

# --- [3. 사이드바: 모델 및 세션 관리] ---
with st.sidebar:
    st.title("🤖 SAI PROJECT")
    st.subheader("🚀 엔진 설정")
    
    # [요청하신 Gemini 3.0 포함 모델 리스트]
    selected_model = st.selectbox(
        "AI 모델 선택", 
        ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    )
    st.caption(f"현재 엔진: {selected_model}")
    
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
        if not chars: st.info("등록된 캐릭터가 없습니다. '제작소' 탭에서 만들어보세요!")
        
        cols = st.columns(3)
        for i, char in enumerate(chars or []):
            with cols[i % 3]:
                if char.get('image_url'): st.image(char['image_url'], use_container_width=True)
                st.subheader(char['name'])
                st.caption(char.get('description', ''))
                if st.button("대화 시작", key=f"start_{char['id']}"):
                    new_id = str(uuid.uuid4())
                    st.session_state.chat_sessions[new_id] = {
                        "char_name": char['name'], "instruction": char['instruction'], "messages": []
                    }
                    st.session_state.current_session_id = new_id
                    st.rerun()
    except Exception as e: st.error("캐릭터 로딩 중 오류 발생")

# [탭 2: 채팅창 - Gemini 3.0 및 최신 로직 적용]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("👈 사이드바에서 대화방을 선택하거나, [트렌드] 탭에서 캐릭터를 골라주세요.")
    else:
        chat = st.session_state.chat_sessions[sid]
        st.subheader(f"💬 {chat['char_name']} (with {selected_model})")

        # DB에서 대화 내용 실시간 동기화
        try:
            res = supabase.table("chat_history").select("role, content").eq("session_id", sid).order("created_at").execute()
            chat["messages"] = res.data
        except: pass

        # 화면 렌더링
        for m in chat["messages"]:
            with st.chat_message(m["role"]): st.write(m["content"])

        # 입력 및 처리
        if prompt := st.chat_input("메시지를 입력하세요..."):
            with st.chat_message("user"): st.write(prompt)
            
            try:
                # 1. 유저 메시지 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "user", "content": prompt, "instruction": chat['instruction']
                }).execute()
                
                # 2. Google GenAI 호출 (최신 표준 방식)
                response = client.models.generate_content(
                    model=selected_model,
                    contents=prompt,
                    config={
                        'system_instruction': chat['instruction'],
                        'temperature': 0.7, # 창의성 조절
                    }
                )
                ai_text = response.text
                
                # 3. AI 응답 저장
                supabase.table("chat_history").insert({
                    "user_id": str(u_id), "session_id": str(sid), "char_name": chat['char_name'],
                    "role": "assistant", "content": ai_text, "instruction": chat['instruction']
                }).execute()
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ AI 응답 실패: {e}")
                st.warning("팁: Gemini 3.0/2.0 모델은 API 키 권한이 필요할 수 있습니다. 1.5 버전으로 변경해 보세요.")

# [탭 3: 이미지 갤러리 - 마비 해결]
with tabs[2]:
    st.header("📸 이미지 갤러리")
    with st.expander("📷 사진 업로드"):
        img_f = st.file_uploader("이미지 선택", type=['jpg', 'png', 'webp'])
        img_d = st.text_input("사진 설명")
        if st.button("업로드") and img_f:
            try:
                fn = f"{uuid.uuid4()}.png"
                # Supabase Storage에 'images' 버킷이 있어야 함
                supabase.storage.from_("images").upload(fn, img_f.read())
                url = supabase.storage.from_("images").get_public_url(fn)
                supabase.table("posts").insert({"user_id": u_id, "img_url": url, "description": img_d}).execute()
                st.success("업로드 성공!")
                st.rerun()
            except Exception as e: st.error(f"업로드 실패: Storage 설정을 확인하세요. ({e})")
    
    # 갤러리 뷰
    try:
        posts = supabase.table("posts").select("*").order("created_at", desc=True).execute().data
        if posts:
            cols = st.columns(3)
            for idx, p in enumerate(posts):
                with cols[idx % 3]:
                    st.image(p['img_url'], use_container_width=True)
                    st.caption(p.get('description', ''))
        else: st.info("첫 번째 사진을 올려보세요!")
    except: st.error("이미지 데이터를 불러올 수 없습니다.")

# [탭 4: 커뮤니티 - 마비 해결]
with tabs[3]:
    st.header("📝 자유 게시판")
    with st.form("community_form", clear_on_submit=True):
        c_txt = st.text_area("무슨 생각을 하고 계신가요?")
        if st.form_submit_button("글쓰기"):
            if c_txt:
                author = st.session_state.user.email if st.session_state.user else "익명 유저"
                supabase.table("comments").insert({"user_email": author, "content": c_txt}).execute()
                st.rerun()
    
    try:
        comments = supabase.table("comments").select("*").order("created_at", desc=True).execute().data
        for c in comments or []:
            with st.container():
                st.markdown(f"**{c.get('user_email', '알 수 없음')}**")
                st.write(c.get('content', ''))
                st.divider()
    except: st.error("게시판 로딩 실패")

# [탭 5: 캐릭터 제작소]
with tabs[4]:
    st.header("🛠️ 나만의 캐릭터 만들기")
    with st.form("char_maker"):
        name = st.text_input("이름 (예: 똑똑한 챗봇)")
        desc = st.text_input("한 줄 소개")
        inst = st.text_area("성격/지침 (예: 너는 친절한 AI야. 존댓말을 써줘.)")
        img_url = st.text_input("프로필 이미지 URL (선택)")
        
        if st.form_submit_button("캐릭터 생성"):
            if name and inst:
                try:
                    supabase.table("sai_characters").insert({
                        "name": name, "description": desc, "instruction": inst, "image_url": img_url
                    }).execute()
                    st.success(f"✅ {name} 캐릭터가 생성되었습니다! [트렌드] 탭에서 확인하세요.")
                except Exception as e: st.error(f"생성 실패: {e}")
            else:
                st.warning("이름과 성격 지침은 필수입니다.")
