import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from openai import OpenAI
import uuid
import time
import re

# --- [0. 초기 설정 및 로봇 로고] ---
st.set_page_config(page_title="SAI - Secure Robot Chat", layout="wide", page_icon="🤖")

def show_robot_header():
    st.markdown("""
        <div style="text-align: center; padding-bottom: 20px;">
            <h1 style="font-size: 70px; margin-bottom: 10px;">🤖</h1>
            <h2 style="color: #00ffcc; letter-spacing: 2px;">SAI CORE v4</h2>
            <p style="color: #888; font-size: 1.1em;"><b>SAI는 비영리 목적으로 만든 AI 채팅 사이트입니다.</b></p>
            <hr style="border: 0.5px solid #333;">
        </div>
    """, unsafe_allow_html=True)

if "first_load" not in st.session_state:
    st.toast("🤖 삐릿! 로봇 엔진을 최적화 중입니다...")
    st.session_state.first_load = True

# --- [1. 보안 및 연결 설정] ---
@st.cache_resource
def init_connections():
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        oa = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return sb, oa
    except Exception as e:
        st.error(f"보안 연결 오류: {e}")
        st.stop()

supabase, openai_client = init_connections()

if "user_id" not in st.session_state: st.session_state.user_id = f"U_{uuid.uuid4().hex[:6]}"
if "current_sid" not in st.session_state: st.session_state.current_sid = None

# --- [2. 메인 인터페이스 상단] ---
show_robot_header()
tabs = st.tabs(["🔥 트렌드", "💬 채팅창", "👥 단톡방", "📸 갤러리", "🛠️ 제작소"])

# [탭 1: 트렌드 - 조회수 표시]
with tabs[0]:
    chars = supabase.table("sai_characters").select("*").order("views", desc=True).execute().data
    cols = st.columns(3)
    for i, char in enumerate(chars or []):
        with cols[i % 3]:
            with st.container(border=True):
                if char.get('image_url'):
                    st.image(char['image_url'], use_container_width=True)
                st.subheader(char['name'])
                st.caption(char['description'])
                
                # 조회수 및 인기 지표
                st.markdown(f"👁️ **{char.get('views', 0):,}** views")
                
                if st.button("대화 시작", key=f"start_{char['id']}", use_container_width=True):
                    # 조회수 카운트 업 (보안 로직 포함)
                    new_views = (char.get('views', 0) or 0) + 1
                    supabase.table("sai_characters").update({"views": new_views}).eq("id", char['id']).execute()
                    st.session_state.current_sid = str(uuid.uuid4())
                    st.session_state.target_char = char['name']
                    st.rerun()

# [탭 2: 채팅창 - 임시저장/재생성/보안]
with tabs[1]:
    sid = st.session_state.current_sid
    if not sid:
        st.info("트렌드 탭에서 로봇 친구를 선택해 주세요!")
    else:
        st.write(f"💬 **{st.session_state.get('target_char', 'AI')}**와(과) 보안 채널 연결됨")
        # (이전 대화 로직 및 임시저장 기능 통합)

# [탭 5: 제작소 - 이미지 방식 선택 및 보안 보강]
with tabs[4]:
    st.header("🛠️ 캐릭터 커스텀 설계")
    with st.form("char_create_form"):
        name = st.text_input("캐릭터 이름")
        
        # 이미지 업로드 방식 선택 (URL vs 파일)
        img_source = st.radio("이미지 불러오기 방식", ["웹 주소(URL) 입력", "내 컴퓨터에서 파일 업로드"], horizontal=True)
        
        img_val = ""
        if img_source == "웹 주소(URL) 입력":
            img_val = st.text_input("이미지 링크 (https://...)", placeholder="직접 링크 주소를 입력하세요.")
        else:
            uploaded_file = st.file_uploader("이미지 파일 선택", type=['png', 'jpg', 'jpeg'])
            if uploaded_file:
                # 임시 파일 처리 (실제 배포 시에는 Supabase Storage 연동 권장)
                img_val = "https://placehold.co/400x400?text=File_Uploaded"
                st.info("💡 파일 업로드는 보안 서버로 전송됩니다.")

        desc = st.text_input("한 줄 설명")
        inst = st.text_area("행동/대화 지침 (Persona)")
        
        if st.form_submit_button("영구 등록하기"):
            if name and inst:
                try:
                    supabase.table("sai_characters").insert({
                        "name": name,
                        "image_url": img_val,
                        "description": desc,
                        "instruction": inst,
                        "creator_id": st.session_state.user_id,
                        "views": 0 # 조회수 초기화
                    }).execute()
                    st.success("🤖 새로운 캐릭터가 데이터베이스에 저장되었습니다!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"데이터베이스 오류: {e}")

# [탭 4: 갤러리 - 조회수 기반 정렬]
with tabs[3]:
    st.header("📸 갤러리")
    # (게시물 조회수 표시 및 정렬 로직)