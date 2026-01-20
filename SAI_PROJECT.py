import streamlit as st
import sqlite3
import os
from datetime import datetime

# =====================
# 기본 설정
# =====================
st.set_page_config(
    page_title="SAI",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DB_PATH = "sai.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =====================
# DB 유틸
# =====================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# =====================
# 자체 AI (placeholder)
# =====================
def local_ai(prompt: str) -> str:
    return f"[SAI Local AI 응답]\n\n{prompt}"

# =====================
# Gemini (API 키 필요)
# =====================
def gemini_ai(prompt: str) -> str:
    # 실제 사용 시 google.generativeai 연동
    return f"[Gemini 응답]\n\n{prompt}"

# =====================
# 세션 초기화
# =====================
if "user_id" not in st.session_state:
    st.session_state.user_id = 1  # 임시 로컬 유저

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "ai_mode" not in st.session_state:
    st.session_state.ai_mode = "Local"

# =====================
# 사이드바
# =====================
with st.sidebar:
    st.header("⚙️ 설정")
    st.radio("AI 선택", ["Local", "Gemini"], key="ai_mode")
    st.divider()

    uploaded = st.file_uploader("파일 업로드", accept_multiple_files=True)
    if uploaded:
        conn = get_db()
        cur = conn.cursor()
        for file in uploaded:
            path = os.path.join(UPLOAD_DIR, file.name)
            with open(path, "wb") as f:
                f.write(file.read())

            cur.execute(
                "INSERT INTO uploads (user_id, filename, filetype, path) VALUES (?, ?, ?, ?)",
                (st.session_state.user_id, file.name, file.type, path)
            )
        conn.commit()
        conn.close()
        st.success("업로드 완료")

# =====================
# 메인 UI
# =====================
st.title("SAI")

# 새 대화 생성
if st.button("➕ 새 대화"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
        (st.session_state.user_id, "새 대화")
    )
    st.session_state.conversation_id = cur.lastrowid
    conn.commit()
    conn.close()

# 대화 선택
conn = get_db()
cur = conn.cursor()
cur.execute("SELECT id, title FROM conversations WHERE user_id=?", (st.session_state.user_id,))
convs = cur.fetchall()
conn.close()

for cid, title in convs:
    if st.button(title or f"대화 {cid}", key=f"c{cid}"):
        st.session_state.conversation_id = cid

# =====================
# 메시지 영역
# =====================
if st.session_state.conversation_id:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id",
        (st.session_state.conversation_id,)
    )
    messages = cur.fetchall()
    conn.close()

    for role, content in messages:
        with st.chat_message(role):
            st.markdown(content)

    prompt = st.chat_input("메시지를 입력하세요")

    if prompt:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
            (st.session_state.conversation_id, prompt)
        )
        conn.commit()

        with st.spinner("🤍 SAI는 비영리 목적입니다.\n잠시만 기다려 주세요…"):
            if st.session_state.ai_mode == "Gemini":
                response = gemini_ai(prompt)
            else:
                response = local_ai(prompt)

        cur.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'ai', ?)",
            (st.session_state.conversation_id, response)
        )
        conn.commit()
        conn.close()

        st.rerun()
else:
    st.info("새 대화를 시작하세요")
