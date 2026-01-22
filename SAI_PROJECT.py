import streamlit as st
from supabase import create_client
import google.generativeai as genai
import uuid

# =====================
# 설정
# =====================
st.set_page_config(page_title="SAI", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# =====================
# 세션 상태
# =====================
if "conversation_id" not in st.session_state:
    conv = supabase.table("conversations").insert({}).execute()
    st.session_state.conversation_id = conv.data[0]["id"]

if "messages" not in st.session_state:
    st.session_state.messages = []

# =====================
# 사이드바
# =====================
st.sidebar.title("🧠 SAI")
st.sidebar.caption("SAI는 비영리 목적입니다")

if st.sidebar.button("새 대화"):
    conv = supabase.table("conversations").insert({}).execute()
    st.session_state.conversation_id = conv.data[0]["id"]
    st.session_state.messages = []
    st.rerun()

# =====================
# UI
# =====================
st.title("🤖 SAI Chat")
st.caption("로그인 없이 사용 가능 · Gemini 기반")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("메시지를 입력하세요")

if user_input:
    # 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": user_input})

    supabase.table("messages").insert({
        "conversation_id": st.session_state.conversation_id,
        "role": "user",
        "content": user_input
    }).execute()

    with st.chat_message("assistant"):
        with st.spinner("AI 응답 생성 중..."):
            response = model.generate_content(user_input).text
            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

    supabase.table("messages").insert({
        "conversation_id": st.session_state.conversation_id,
        "role": "assistant",
        "content": response
    }).execute()
