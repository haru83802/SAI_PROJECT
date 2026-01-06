class SAIMemory:
    def __init__(self, mode="basic"):
        self.mode = mode
        self.history = []  # 전체 대화 로그
        self.summary = ""  # Story용 요약

    def add_chat(self, speaker, message):
        self.history.append({"speaker": speaker, "message": message})

    def get_context(self):
        if self.mode == "pro":
            # Pro: 최근 며칠간의 대화를 시뮬레이션하기 위해 많은 양 반환
            return self.history[-50:] 
        elif self.mode == "story":
            # Story: 요약본 + 최근 대화 3개
            return f"[줄거리]: {self.summary}\n[최근]: {self.history[-3:]}"
        elif self.mode == "rollplaying":
            # RP: 최근 흐름 10개
            return self.history[-10:]
        return self.history[-5:] # Basic
