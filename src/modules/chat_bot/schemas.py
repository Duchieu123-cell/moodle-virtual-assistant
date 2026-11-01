from pydantic import BaseModel

class ChatTurn(BaseModel):
    user_message: str
    chatbot_response: str
    
class Message(BaseModel):
    message: str
    user_id: int
    role: str
    chat_history: list[ChatTurn] = []
     
def format_chat_history(history: list[ChatTurn]) -> str:
    """
    Hàm này chuyển đổi danh sách lịch sử thành một chuỗi văn bản thuần túy.
    Ví dụ:
    User: Tôi đang học khóa nào?
    Bot: Bạn đang học khóa Toán và Lý.
    """
    if not history:
        return "Không có lịch sử trò chuyện trước đó."
    
    formatted_text = ""
    for turn in history:
        formatted_text += f"User: {turn.user_message}\n"
        formatted_text += f"Bot: {turn.chatbot_response}\n\n"
    
    return formatted_text.strip()


