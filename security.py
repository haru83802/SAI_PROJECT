import re
import streamlit as st
import time

class SAISecurity:
    def __init__(self):
        self.blacklist_words = ["drop table", "delete from", "<script>", "union select"]
        if "banned_ips" not in st.session_state:
            st.session_state.banned_ips = set()

    def get_remote_ip(self):
        try:
            from streamlit.web.server.websocket_headers import _get_websocket_headers
            headers = _get_websocket_headers()
            return headers.get("X-Forwarded-For", "127.0.0.1").split(",")[0]
        except: return "127.0.0.1"

    def is_banned(self):
        return self.get_remote_ip() in st.session_state.banned_ips

    def validate_image(self, uploaded_file):
        """이미지 보안 검사: 확장자 및 용량 제한"""
        if uploaded_file is not None:
            # 1. 용량 제한 (5MB)
            if uploaded_file.size > 5 * 1024 * 1024:
                return False, "파일이 너무 큽니다 (최대 5MB)"
            # 2. 확장자 제한
            allowed_types = ["image/png", "image/jpeg", "image/jpg"]
            if uploaded_file.type not in allowed_types:
                return False, "PNG, JPG 파일만 업로드 가능합니다."
        return True, "Safe"

    def sanitize_text(self, text):
        if not text: return ""
        return re.sub(r'<.*?>|[;|$%]', '', text)[:500]

    def check_malicious(self, text):
        lower_text = text.lower()
        for word in self.blacklist_words:
            if word in lower_text:
                user_ip = self.get_remote_ip()
                st.session_state.banned_ips.add(user_ip)
                return False, f"위험 감지: IP가 차단되었습니다."
        return True, "Safe"

sai_guard = SAISecurity()