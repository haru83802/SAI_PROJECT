import re
import streamlit as st

class SAISecurity:
    def __init__(self):
        self.blacklist_words = ["drop table", "delete from", "<script>", "union select"]

    def get_remote_ip(self):
        """최신 Streamlit 방식(1.30+)으로 접속자 IP 가져오기"""
        try:
            # st.context.headers를 통해 안전하게 IP 추출
            headers = st.context.headers
            if "X-Forwarded-For" in headers:
                return headers["X-Forwarded-For"].split(",")[0]
            return "127.0.0.1" # 로컬 환경
        except:
            return "Unknown"

    def is_banned(self):
        """현재 접속자가 차단 리스트에 있는지 확인"""
        if "banned_ips" not in st.session_state:
            st.session_state.banned_ips = set()
        user_ip = self.get_remote_ip()
        return user_ip in st.session_state.banned_ips

    def sanitize_text(self, text):
        """입력값 세척"""
        if not text: return ""
        clean = re.sub(r'<.*?>|[;|$%]', '', text)
        return clean[:1000] # 길이 제한

    def check_malicious(self, text):
        """악성 패턴 탐지 및 자동 차단"""
        if not text: return True, ""
        lower_text = text.lower()
        for word in self.blacklist_words:
            if word in lower_text:
                if "banned_ips" not in st.session_state:
                    st.session_state.banned_ips = set()
                st.session_state.banned_ips.add(self.get_remote_ip())
                return False, f"보안 위협({word})이 감지되어 IP가 차단되었습니다."
        return True, "Safe"

sai_guard = SAISecurity()