# ---------------------------------
# 기본 설정
# ---------------------------------
st.set_page_config(page_title="SAI", layout="centered")

with st.spinner("SAI는 비영리 목적입니다"):
    pass

# ---------------------------------
# 연결
# ---------------------------------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini = genai.GenerativeModel("models/gemini-1.5-flash")

HF_TOKEN = st.secrets.get("HF_TOKEN")

# ---------------------------------
# 세션
# ---------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# ---------------------------------
# 로그인
# ---------------------------------
if not st.session_state.user:
    st.title("🔐 SAI 로그인")
    email = st.text_input("이메일")
    if st.button("매직 링크 로그인"):
        supabase.auth.sign_in_with_otp({"email": email})
        st.info("이메일을 확인하세요.")
    st.stop()

st.session_state.user = supabase.auth.get_user().user
user_id = st.session_state.user.id

# ---------------------------------
# 사이드바
# ---------------------------------
with st.sidebar:
    st.subheader("⚙️ 설정")

    ai_type = st.selectbox(
        "AI 선택",
        ["Gemini", "HuggingFace", "Local"]
    )

    copilot = st.checkbox("🧠 Copilot AI 사용")

    chars = supabase.table("characters") \
        .select("*") \
        .or_(f"owner_id.eq.{user_id},is_public.eq.true") \
        .execute().data

    char_map = {c["name"]: c for c in chars}
    char_name = st.selectbox("캐릭터", char_map.keys())

    if st.button("➕ 새 대화"):
        conv = supabase.table("conversations").insert({
            "user_id": user_id,
            "character_id": char_map[char_name]["id"],
            "ai_type": ai_type
        }).execute().data[0]
        st.session_state.conversation_id = conv["id"]
        st.rerun()

    if st.button("🚪 로그아웃"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# ---------------------------------
# 캐릭터 제작
# ---------------------------------
st.subheader("🛠 캐릭터 제작 (무제한 프롬프트)")

with st.form("char_form"):
    cname = st.text_input("이름")
    cinst = st.text_area("프롬프트 (제한 없음)", height=200)
    public = st.checkbox("마켓 공개")

    if st.form_submit_button("생성"):
        supabase.table("characters").insert({
            "owner_id": user_id,
            "name": cname,
            "instruction": cinst,
            "is_public": public
        }).execute()
        st.success("캐릭터 생성 완료")
        st.rerun()

# ---------------------------------
# 캐릭터 마켓
# ---------------------------------
st.subheader("🛒 캐릭터 마켓")

market_chars = supabase.table("characters") \
    .select("*") \
    .eq("is_public", True) \
    .execute().data

for c in market_chars:
    with st.expander(f"{c['name']}"):
        st.write(c["instruction"][:200] + "...")
        if st.button("📥 내 캐릭터로 복사", key=c["id"]):
            supabase.table("characters").insert({
                "owner_id": user_id,
                "name": c["name"],
                "instruction": c["instruction"],
                "original_id": c["id"],
                "is_public": False
            }).execute()
            st.success("복사 완료")
            st.rerun()

# ---------------------------------
# 채팅
# ---------------------------------
if not st.session_state.conversation_id:
    st.info("대화를 시작하세요.")
    st.stop()

msgs = supabase.table("messages") \
    .select("*") \
    .eq("conversation_id", st.session_state.conversation_id) \
    .order("created_at") \
    .execute().data

for m in msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("메시지 입력")

if prompt:
    supabase.table("messages").insert({
        "conversation_id": st.session_state.conversation_id,
        "role": "user",
        "content": prompt
    }).execute()

    char = char_map[char_name]
    system_prompt = f"{char['instruction']}\n\n{prompt}"

    # -------- AI 분기 --------
    if ai_type == "Gemini":
        reply = gemini.generate_content(system_prompt).text

    elif ai_type == "HuggingFace":
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        res = requests.post(
            "https://api-inference.huggingface.co/models/google/flan-t5-base",
            headers=headers,
            json={"inputs": system_prompt}
        )
        reply = res.json()[0]["generated_text"]

    else:
        reply = f"[LOCAL AI]\n{prompt[::-1]}"

    # -------- Copilot --------
    if copilot:
        improve = gemini.generate_content(
            f"다음 답변을 개선해줘:\n{reply}"
        ).text
        reply += f"\n\n---\n🧠 Copilot 개선안:\n{improve}"

    supabase.table("messages").insert({
        "conversation_id": st.session_state.conversation_id,
        "role": "assistant",
        "content": reply
    }).execute()

    st.rerun()

