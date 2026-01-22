import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import uuid

# ======================
# 페이지 설정 (모바일 대응)
# ======================
st.set_page_config(
    page_title="SAI",
    layout="wide"
)

# ======================
# Secrets
# ======================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# ======================
# Clients
# ======================
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-pro")

# ======================
# Session Init
# ======================
if "user_id" not in st.session_state:
    user = supabase.table("users").select("id").limit(1).execute()
    if user.data:
        st.session_state.user_id = user.data[0]["id"]
    else:
        new_user = supabase.table("users").insert({
            "provider": "local",
            "provider_id": str(uuid.uuid4()),
            "display_name": "Guest"
        }).execute()
        st.session_state.user_id = new_user.data[0]["id"]

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# ======================
# Sidebar
# ======================
with st.sidebar:
    st.title("🧬 SAI")

    st.caption("비영리 목적 AI 프로젝트")

    st.divider()
    st.subheader("내 대화")

    conversations = (
        supabase
        .table("conversations")
        .select("id, title")
        .eq("user_id", st.session_state.user_id)
        .order("created_at", desc=True)
        .execute()
    ).data

    for c in conversations:
        if st.button(c["title"] or f"대화 {c['id']}", key=str(c["id"])):
            st.session_state.conversation_id = c["id"]
            st.rerun()

    if st.button("➕ 새 대화"):
        conv = supabase.table("conversations").insert({
            "user_id": st.session_state.user_id,
            "title": "새 대화"
        }).execute()
        st.session_state.conversation_id = conv.data[0]["id"]
        st.rerun()

# ======================
# Main
# ======================
st.title("💬 SAI Chat")

if not st.session_state.conversation_id:
    st.info("왼쪽에서 새 대화를 시작하세요.")
    st.stop()

messages = (
    supabase
    .table("messages")
    .select("role, content")
    .eq("conversation_id", st.session_state.conversation_id)
    .order("created_at")
    .execute()
).data

for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("메시지를 입력하세요")

if user_input:
    # 유저 메시지 저장
    supabase.table("messages").insert({
        "conversation_id": st.session_state.conversation_id,
        "role": "user",
        "content": user_input
    }).execute()

    with st.chat_message("assistant"):
        with st.spinner("🤍 SAI는 비영리 목적입니다.\n잠시만 기다려 주세요…"):
            response = gemini.generate_content(user_input).text
            st.markdown(response)

    # AI 메시지 저장
    supabase.table("messages").insert({
        "conversation_id": st.session_state.conversation_id,
        "role": "assistant",
        "content": response
    }).execute()

    st.rerun()
