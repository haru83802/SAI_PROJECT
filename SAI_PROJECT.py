# =============================
# SAI LOCAL AI – STREAMLIT SITE
# Single-file Version
# =============================

import streamlit as st
import uuid
import html

import ollama
import faiss
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# =============================
# Page Config
# =============================
st.set_page_config(
    page_title="SAI Local AI",
    page_icon="🤖",
    layout="wide",
)

# =============================
# CSS (Site UI)
# =============================
st.markdown(
    """
    <style>
    body { background-color: #0e1117; color: #e6e6e6; }
    header, footer { visibility: hidden; }

    .chat-user{display:flex;justify-content:flex-end;padding:6px 0}
    .chat-user .bubble{
        background:linear-gradient(135deg,#6c5ce7,#8e7cff);
        color:white;
        padding:14px 18px;
        border-radius:22px 22px 6px 22px;
        max-width:70%;
        word-break:break-word;
    }

    .chat-ai{display:flex;justify-content:flex-start;padding:6px 0}
    .chat-ai .bubble{
        background:#1f2128;
        color:#e5e7eb;
        padding:18px 20px;
        border-radius:22px 22px 22px 6px;
        max-width:72%;
        line-height:1.6;
        word-break:break-word;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================
# Utility
# =============================
def safe(text: str) -> str:
    """XSS 방어"""
    return html.escape(text)

# =============================
# Session Init
# =============================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "embedder" not in st.session_state:
    st.session_state.embedder = SentenceTransformer("all-MiniLM-L6-v2")

if "faiss_index" not in st.session_state:
    dim = 384
    st.session_state.faiss_index = faiss.IndexFlatL2(dim)
    st.session_state.memory_texts = []

# =============================
# Memory Functions
# =============================
def add_memory(text: str):
    vec = st.session_state.embedder.encode([text]).astype("float32")
    st.session_state.faiss_index.add(vec)
    st.session_state.memory_texts.append(text)

def search_memory(query: str, k: int = 3) -> str:
    if not st.session_state.memory_texts:
        return ""
    qvec = st.session_state.embedder.encode([query]).astype("float32")
    _, idx = st.session_state.faiss_index.search(qvec, k)
    return "\n".join(
        st.session_state.memory_texts[i]
        for i in idx[0]
        if i < len(st.session_state.memory_texts)
    )

def is_repeat(user_input: str, threshold: float = 0.88) -> bool:
    if not st.session_state.memory_texts:
        return False
    vec = st.session_state.embedder.encode([user_input])
    for past in st.session_state.memory_texts[-5:]:
        pvec = st.session_state.embedder.encode([past])
        sim = cosine_similarity(vec, pvec)[0][0]
        if sim > threshold:
            return True
    return False

# =============================
# Local AI Engine (Ollama)
# =============================
def local_ai(user_input: str) -> str:
    related_memory = search_memory(user_input)

    system_prompt = (
        "같은 내용을 반복하지 말고 새로운 관점으로 답하라."
        if is_repeat(user_input)
        else "차분하고 논리적인 AI 어시스턴트다."
    )

    prompt = f"""
[관련 기억]
{related_memory}

[사용자 질문]
{user_input}

중복 없이 자연스럽게 대답하라.
"""

    res = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    answer = res["message"]["content"]

    add_memory(user_input)
    add_memory(answer)

    return answer

# =============================
# UI – Header
# =============================
st.title("🧠 SAI Local AI")
st.caption("Streamlit 사이트 전용 · 로컬 AI · 로그인 없음")

# =============================
# UI – Chat History
# =============================
for m in st.session_state.messages:
    if m["role"] == "user":
        st.markdown(
            f"<div class='chat-user'><div class='bubble'>{safe(m['content'])}</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='chat-ai'><div class='bubble'>{safe(m['content'])}</div></div>",
            unsafe_allow_html=True,
        )

# =============================
# Input
# =============================
user_input = st.chat_input("메시지를 입력하세요")

if user_input:
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )

    with st.spinner("AI가 생각 중입니다..."):
        reply = local_ai(user_input)

    st.session_state.messages.append(
        {"role": "assistant", "content": reply}
    )

    # UI 메시지 제한
    st.session_state.messages = st.session_state.messages[-40:]

    st.rerun()

# =============================
# Footer
# =============================
st.caption("SAI는 비영리 로컬 AI 프로젝트입니다.")
