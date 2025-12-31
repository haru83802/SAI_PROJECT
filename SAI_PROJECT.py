import streamlit as st
from supabase import create_client, Client
import uuid
from sai_processor import SAIEngine

# --- [초기 설정] ---
st.set_page_config(page_title="SAI Ultimate v3", layout="wide")
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

if "user_id" not in st.session_state: st.session_state.user_id = f"U_{uuid.uuid4().hex[:4]}"
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# --- [상단 공지 & 개발자 코멘트] ---
st.markdown("<div style='background:#222; padding:10px; border-radius:10px; color:#00ffcc;'>📢 <b>SYSTEM:</b> @캐릭터 이름으로 대화 상대를 즉시 교체할 수 있습니다. 🔄 아이콘은 답변을 재생성합니다.</div>", unsafe_allow_html=True)

# --- [사이드바: 유저 설정 & 호감도] ---
with st.sidebar:
    st.title("🤖 SAI PROFILE")
    st.write(f"접속 중: **{st.session_state.user_id}**")
    
    # [다화자 기능용 캐릭터 리스트]
    chars = supabase.table("sai_characters").select("*").execute().data
    char_map = {c['name']: c for c in chars}
    
    st.divider()
    st.subheader("⚙️ 유저 커스텀 설정")
    user_nickname = st.text_input("당신을 부를 호칭", value="여행자")
    
    st.divider()
    st.info("💡 **Dev Note:** () 안의 행동 묘사는 AI의 몰입도를 높입니다.")

# --- [메인 탭] ---
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "🛠️ 캐릭터 생성"])

# [탭 2: 채팅창]
with tabs[1]:
    sid = st.session_state.current_session_id
    if not sid:
        st.info("@캐릭터이름을 입력하거나 트렌드에서 선택하세요.")
    else:
        # 데이터 로드
        messages = supabase.table("chat_history").select("*").eq("session_id", sid).order("created_at").execute().data
        char_name = messages[0]['char_name'] if messages else "알 수 없음"
        current_char = char_map.get(char_name, {})
        
        # [상단 캐릭터 프로필 & 호감도]
        col1, col2 = st.columns([1, 4])
        with col1:
            img = current_char.get('image_url', "https://via.placeholder.com/150")
            st.image(img, width=100)
        with col2:
            st.subheader(f"{char_name}")
            affinity = messages[-1]['affinity_score'] if messages else current_char.get('base_affinity', 50)
            st.progress(affinity / 100, text=f"❤️ 호감도: {affinity}%")

        # 대화 출력
        for i, m in enumerate(messages):
            with st.chat_message(m["role"]):
                st.write(m["content"])
                # [답변 재생성 아이콘] assistant의 마지막 메시지에만 표시
                if m["role"] == "assistant" and i == len(messages)-1:
                    if st.button("🔄", key=f"retry_{i}"):
                        # 마지막 답변 삭제 후 재실행 로직 (간략화)
                        supabase.table("chat_history").delete().eq("id", m['id']).execute()
                        st.rerun()

        # 입력창
        if prompt := st.chat_input("메시지 입력 (@캐릭터로 교체)..."):
            # [@캐릭터 교체 기능]
            if prompt.startswith("@") and " " in prompt:
                target_name, new_prompt = prompt[1:].split(" ", 1)
                if target_name in char_map:
                    st.session_state.current_session_id = str(uuid.uuid4())
                    char_name = target_name
                    prompt = new_prompt
            
            # 메시지 저장 및 AI 호출
            with st.chat_message("user"): st.write(prompt)
            
            engine = SAIEngine(st.sidebar.selectbox("모델", ["gemini-1.5-flash", "gpt-4o"], key="m"), 
                               current_char['instruction'], affinity)
            
            ai_resp = engine.generate(prompt, messages)
            
            # DB 저장 (호감도 로직 포함 가능)
            supabase.table("chat_history").insert({
                "user_id": st.session_state.user_id, "session_id": sid,
                "char_name": char_name, "role": "user", "content": prompt,
                "instruction": current_char['instruction'], "affinity_score": affinity
            }).execute()
            
            supabase.table("chat_history").insert({
                "user_id": st.session_state.user_id, "session_id": sid,
                "char_name": char_name, "role": "assistant", "content": ai_resp,
                "instruction": current_char['instruction'], "affinity_score": affinity
            }).execute()
            st.rerun()

# [탭 3: 제작자 설정]
with tabs[2]:
    st.header("🛠️ 캐릭터 제작소")
    with st.form("make"):
        n = st.text_input("이름")
        img_url = st.text_input("이미지 URL (직접 링크)")
        base_aff = st.slider("시작 호감도", 0, 100, 50)
        inst = st.text_area("지침")
        if st.form_submit_button("등록"):
            supabase.table("sai_characters").insert({
                "name": n, "image_url": img_url, "base_affinity": base_aff, 
                "instruction": inst, "creator_id": st.session_state.user_id
            }).execute()
            st.success("캐릭터가 생성되었습니다.")