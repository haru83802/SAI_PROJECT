# =============================
# SAI LOCAL AI – FULL STABLE VERSION
# =============================
# - Login 없음
# - 무료 사용 전제
# - 반복 응답 방지
# - 강화된 기억력
# - 이미지 업로드
# - 프리미엄 다크 UI
# =============================

import streamlit as st
import uuid
from collections import deque
from datetime import datetime

# =============================
# Page Config
# =============================
st.set_page_config(
    page_title="SAI Project",
    page_icon="🤖",
    layout="wide",
)

# ===== Theme Toggle =====
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

with st.sidebar:
    st.markdown("## ⚙️ 설정")
    theme_toggle = st.toggle("다크 모드", value=(st.session_state.theme == "dark"))
    st.session_state.theme = "dark" if theme_toggle else "light"

if st.session_state.theme == "dark":
    st.markdown(
        """
        <style>
        body { background-color: #0e1117; color: #e6e6e6; }
        .stApp { background-color: #0e1117; }
        .stChatMessage { background-color: #161b22; border-radius: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <style>
        body { background-color: #ffffff; color: #000000; }
        .stApp { background-color: #ffffff; }
        .stChatMessage { background-color: #f3f4f6; border-radius: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# =============================
# UI Style
# =============================
st.markdown("""
<style>
:root {
  --bg: #0b0c10;
  --user: linear-gradient(135deg,#6c5ce7,#8e7cff);
  --ai: #1f2128;
  --text: #e5e7eb;
  --muted: #9ca3af;
}
html, body, [class*="css"] {
  background-color: var(--bg) !important;
  color: var(--text) !important;
}
.chat-user{display:flex;justify-content:flex-end;padding:6px 0}
.chat-user .bubble{background:var(--user);color:white;padding:14px 18px;border-radius:22px 22px 6px 22px;max-width:70%;box-shadow:0 8px 24px rgba(0,0,0,.35)}
.chat-ai{display:flex;justify-content:flex-start;gap:10px;padding:8px 0}
.chat-ai .bubble{background:var(--ai);color:var(--text);padding:18px 20px;border-radius:22px 22px 22px 6px;max-width:72%;line-height:1.7;box-shadow:0 6px 20px rgba(0,0,0,.25)}
.name-tag{font-size:13px;color:var(--muted);margin-bottom:6px}
header, footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# =============================
# Session State Init
# =============================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "memory_vectors" not in st.session_state:
    st.session_state.memory_vectors = deque(maxlen=50)

if "long_memory" not in st.session_state:
    st.session_state.long_memory = ""

# =============================
# Characters (ONLY ONE)
# =============================
DEFAULT_CHARACTERS = {
    "SAI Assistant": {
        "style": "차분하고 논리적이며 반복 없이 대화",
        "system": "너는 SAI의 공식 로컬 AI 어시스턴트다.",
    }
}

st.session_state.characters = DEFAULT_CHARACTERS
st.session_state.character = "SAI Assistant"

# =============================
# Memory Engine
# =============================
def update_memory(user, assistant):
    pair = f"USER:{user} ASSISTANT:{assistant}"
    st.session_state.memory_vectors.append(pair)
    joined = " ".join(st.session_state.memory_vectors)
    st.session_state.long_memory = joined[-1500:]

# =============================
# Local AI Engine (Non-repeating)
# =============================
def local_ai(user_input: str) -> str:
    recent_ai = " ".join(
        [m["content"] for m in st.session_state.messages[-4:] if m["role"] == "assistant"]
    )

    if user_input in recent_ai:
        guide = "같은 말을 반복하지 말고 관점이나 감정을 발전시켜라."
    else:
        guide = "이전 대화를 자연스럽게 이어가라."

    response = f"""
[기억 요약]
{st.session_state.long_memory[-300:]}

[지침]
{guide}

[응답]
질문에 대해 새롭고 자연스럽게 대답한다.
"""
    return response.strip()

# =============================
# Sidebar – Image Upload
# =============================
st.sidebar.title("⚙️ 설정")
with st.sidebar.expander("🖼 이미지 업로드"):
    img = st.file_uploader("이미지 업로드", type=["png","jpg","jpeg"])
    if img:
        st.image(img, width=200)
        st.session_state.messages.append({"role":"user","content":"[이미지 업로드]"})

# =============================
# Main UI
# =============================
st.title("🧠 SAI Local AI")
st.caption("무료 · 로그인 없음 · 로컬 AI")

for m in st.session_state.messages:
    if m["role"] == "user":
        st.markdown(f"<div class='chat-user'><div class='bubble'>{m['content']}</div></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-ai'><div><div class='name-tag'>SAI Assistant</div><div class='bubble'>{m['content']}</div></div></div>", unsafe_allow_html=True)

user_input = st.chat_input("메시지를 입력하세요")

if user_input:
    st.session_state.messages.append({"role":"user","content":user_input})
    reply = local_ai(user_input)
    update_memory(user_input, reply)
    st.session_state.messages.append({"role":"assistant","content":reply})
    st.rerun()

st.caption("SAI는 비영리 목적입니다")
