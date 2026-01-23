# SAI Local AI v2
# Features: (2) Supabase optional storage, (3) Character Market (basic), (4) Enhanced Memory
# Free, no-login required

import streamlit as st
import uuid
from datetime import datetime
from typing import List, Dict

# =============================
# Page Config
# =============================
st.set_page_config(page_title="SAI Local AI v2", page_icon="🧠", layout="wide")

# =============================
# =============================
# UI Style (Premium Dark Chat UI)
# =============================
st.markdown("""
<style>
:root {
  --bg: #0b0c10;
  --panel: #14151a;
  --user: linear-gradient(135deg,#6c5ce7,#8e7cff);
  --ai: #1f2128;
  --text: #e5e7eb;
  --muted: #9ca3af;
}

html, body, [class*="css"] {
  background-color: var(--bg) !important;
  color: var(--text) !important;
}

.chat-user {
  display:flex;
  justify-content:flex-end;
  padding:6px 0;
}
.chat-user .bubble {
  background: var(--user);
  color:white;
  padding:14px 18px;
  border-radius:22px 22px 6px 22px;
  max-width:70%;
  font-size:16px;
  box-shadow:0 8px 24px rgba(0,0,0,.35);
}

.chat-ai {
  display:flex;
  justify-content:flex-start;
  gap:10px;
  padding:8px 0;
}

.chat-ai .bubble {
  background: var(--ai);
  color:var(--text);
  padding:18px 20px;
  border-radius:22px 22px 22px 6px;
  max-width:72%;
  font-size:16px;
  line-height:1.7;
  box-shadow:0 6px 20px rgba(0,0,0,.25);
}

.name-tag {
  font-size:13px;
  color:var(--muted);
  margin-bottom:6px;
}

header, footer { visibility: hidden; }

.stChatInput {
  position: sticky;
  bottom: 0;
  background: linear-gradient(to top, var(--bg), transparent);
}
</style>
""", unsafe_allow_html=True)


# =============================
# Optional Supabase (API key based)
# =============================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
use_supabase = bool(SUPABASE_URL and SUPABASE_KEY)

if use_supabase:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        use_supabase = False

# =============================
# Session State
# =============================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages: List[Dict] = []

if "long_memory" not in st.session_state:
    st.session_state.long_memory = ""  # summarized memory

if "short_memory" not in st.session_state:
    st.session_state.short_memory = []  # last turns

if "character" not in st.session_state:
    st.session_state.character = "케리드라"

# =============================
# Characters (Default + Market)
# =============================
DEFAULT_CHARACTERS = {
    "SAI Assistant": {
        "origin": "Original",
        "style": "차분하고 정확한 말투, 불필요한 반복 없이 응답",
        "system": "너는 SAI의 공식 로컬 AI 어시스턴트다.",
        "public": True
    }
}
}

if "characters" not in st.session_state:
    st.session_state.characters = DEFAULT_CHARACTERS.copy()

# =============================
# SAI Modes
# =============================
SAI_MODES = {
    "SAI Chat": "자연스럽고 간결",
    "SAI Story": "서사와 묘사 강화",
    "SAI Roleplaying": "캐릭터 몰입 1인칭",
    "SAI Pro": "논리적·구조적"
}

# =============================
# Memory Engine (Vector-like)
# =============================
from collections import deque

if "memory_vectors" not in st.session_state:
    st.session_state.memory_vectors = deque(maxlen=50)


def update_memory(user, assistant):
    pair = f"USER:{user} ASSISTANT:{assistant}"
    st.session_state.memory_vectors.append(pair)

    # long memory summary
    joined = " ".join(st.session_state.memory_vectors)
    st.session_state.long_memory = joined[-1500:]

# =============================
# Local AI Engine (Replaceable)
# =============================
def local_ai(user_input: str, mode: str, char_name: str) -> str:
    char = st.session_state.characters[char_name]

    # repetition guard
    recent = " ".join([m["content"] for m in st.session_state.messages[-4:] if m["role"] == "assistant"])

    base_prompt = f"너는 {char_name}다. 말투: {char['style']}. 모드: {mode}."

    if user_input in recent:
        tone = "같은 말을 반복하지 말고, 새로운 관점이나 감정을 추가해 응답하라."
    else:
        tone = "이전 맥락을 자연스럽게 이어가되 표현을 반복하지 말라."

    response = (
        f"{base_prompt}
"
        f"기억 요약: {st.session_state.long_memory[-300:]}
"
        f"지침: {tone}
"
        f"응답: {user_input}에 대해 케리드라의 관점에서 상황과 감정을 발전시켜 말한다."
    )
    return response

# =============================
# Save to Supabase (optional)
# =============================
def save_message(role, content):
    if not use_supabase:
        return
    try:
        supabase.table("conversations").insert({
            "session_id": st.session_state.session_id,
            "role": role,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        pass

# =============================
# Sidebar
# =============================
st.sidebar.title("⚙️ 설정")

st.session_state.character = st.sidebar.selectbox(
    "캐릭터",
    list(st.session_state.characters.keys())
)

mode = st.sidebar.radio("모드", list(SAI_MODES.keys()))

search = st.sidebar.text_input("🔍 대화 검색")

# =============================
# Image Upload
# =============================
with st.sidebar.expander("🖼 이미지 업로드"):
    uploaded_img = st.file_uploader("이미지 업로드", type=["png","jpg","jpeg"])
    if uploaded_img:
        st.session_state.messages.append({
            "role": "user",
            "content": "[이미지 업로드]"
        })
        st.image(uploaded_img, width=200)

# =============================
# Main
# =============================
st.title("🧠 SAI Local AI v2")
st.caption("무료 · 로그인 없음 · 기억력 강화 · 캐릭터 마켓")

# Chat history
for m in st.session_state.messages:
    if search and search not in m["content"]:
        continue

    if m["role"] == "user":
        st.markdown(f"<div class='chat-user'><div class='bubble'>{m['content']}</div></div>", unsafe_allow_html=True)
    else:
        char = st.session_state.character
        st.markdown(f"<div class='chat-ai'><div><div class='name-tag'>{char}</div><div class='bubble'>{m['content']}</div></div></div>", unsafe_allow_html=True)

# Input
user_input = st.chat_input("메시지를 입력하세요")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_message("user", user_input)

    with st.spinner("SAI 처리 중..."):
        reply = local_ai(user_input, mode, st.session_state.character)
        update_memory(user_input, reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    save_message("assistant", reply)

    st.rerun()

# =============================
# Character Market
# =============================
with st.expander("🛒 캐릭터 마켓 / 제작"):
    st.subheader("새 캐릭터 제작")
    n = st.text_input("이름")
    o = st.text_input("출처")
    s = st.text_area("말투/성격")
    sy = st.text_area("시스템 프롬프트")
    pub = st.checkbox("공개", value=True)

    if st.button("생성") and n:
        st.session_state.characters[n] = {
            "origin": o,
            "style": s,
            "system": sy,
            "public": pub
        }
        st.success(f"{n} 생성 완료")

    st.markdown("---")
    st.subheader("공개 캐릭터")
    for name, c in st.session_state.characters.items():
        if c.get("public"):
            st.markdown(f"**{name}** · {c['origin']}")

st.markdown("---")
st.caption("SAI Local AI v2")
