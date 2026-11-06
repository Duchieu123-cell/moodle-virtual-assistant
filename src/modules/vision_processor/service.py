from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import base64
import io
from PIL import Image
from src.core.config import settings
from src.core.exception import InternalServerError

GROQ_API_KEY = settings.GROQ_API_KEY

# Prompt tối ưu riêng cho Slide bài giảng & Giáo trình phục vụ RAG
SYSTEM_PROMPT = """Bạn là chuyên gia phân tích tài liệu kỹ thuật và học thuật cho hệ thống RAG.
Hình ảnh được cung cấp là một trang Slide bài giảng hoặc một trang Giáo trình.
Nhiệm vụ của bạn là trích xuất thông tin từ CÁC THÀNH PHẦN TRỰC QUAN (Sơ đồ, Lưu đồ, Biểu đồ, Bảng biểu, Công thức toán học/hóa học, hoặc Ảnh chụp màn hình code/kiến trúc).

QUY TẮC BẮT BUỘC:
1. KHÔNG chép lại các đoạn văn bản/gạch đầu dòng thông thường đã hiển thị rõ trên trang (vì hệ thống đã trích xuất text riêng), chỉ dùng chúng để hiểu ngữ cảnh.
2. Nếu có Lưu đồ (Flowchart) / Sơ đồ kiến trúc (Architecture Diagram): Mô tả rõ luồng đi, các thành phần và mối quan hệ nhân quả/thứ tự (VD: A -> B -> C).
3. Nếu có Biểu đồ (Chart/Graph): Nêu rõ tên biểu đồ, ý nghĩa các trục (X, Y), số liệu nổi bật và xu hướng chính.
4. Nếu có Bảng biểu (Table) hoặc Công thức phức tạp: Chuyển đổi chính xác sang định dạng Markdown Table hoặc LaTeX.
5. Nếu trang CHỈ chứa hình ảnh trang trí, ảnh minh họa chung chung (con người, phong cảnh, logo, icon) không mang kiến thức học thuật, hoặc không có biểu đồ/sơ đồ nào có ý nghĩa: Chỉ trả về đúng từ khóa: SKIP_IMAGE (không giải thích gì thêm).
"""

class VisionProcessService:
    # Khởi tạo model 1 lần ở cấp độ Class, bật max_retries để chống lỗi Rate Limit (429) của Groq
    _vision_model = ChatGroq(
        model_name="qwen/qwen3.8-27b", # Lưu ý: Đảm bảo tên model chính xác theo tài liệu hiện hành của Groq
        groq_api_key=GROQ_API_KEY,
        temperature=0.0,               # Temperature = 0 để đảm bảo tính chính xác cho RAG
        max_retries=3
    )

    @staticmethod
    def _encode_image_to_base64(pil_image: Image.Image, max_size: tuple = (1568, 1568)) -> str:
        """Thu nhỏ ảnh nếu quá lớn và chuyển đổi sang Base64 JPEG"""
        buffered = io.BytesIO()
        
        # Copy để không làm ảnh hưởng object gốc và thu nhỏ giữ nguyên tỷ lệ (aspect ratio)
        img = pil_image.copy()
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img.save(buffered, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    @staticmethod
    async def describe_image(pil_image: Image.Image) -> str:
        """
        Gửi ảnh tới Vision LLM. 
        Trả về chuỗi mô tả, chuỗi rỗng "" nếu cần bỏ qua, hoặc "error" nếu lỗi API.
        """
        try:
            base64_image = VisionProcessService._encode_image_to_base64(pil_image)
            
            message = HumanMessage(
                content=[
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ]
            )
            
            response = await VisionProcessService._vision_model.ainvoke([message])
            content = response.content.strip()

            # Bắt cờ SKIP_IMAGE hoặc các phản hồi rỗng
            if not content or "SKIP_IMAGE" in content or content in ('""', "''"):
                return ""
                
            return content
            
        except Exception as e:
            print(f"Lỗi khi xử lý hình ảnh bằng Vision LLM: {e}")
            return "error"