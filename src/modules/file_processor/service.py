from src.modules.vision_processor.service import VisionProcessService
from langchain_core.documents import Document
from collections import Counter
from PIL import Image
import unicodedata
import pymupdf
import io
import re


# Chỉ giữ lại các tiêu đề thực sự đặc trưng cho trang mục lục / tài liệu tham khảo độc lập
GARBAGE_PAGE_TITLES = [
    "mục lục",
    "table of contents",
    "danh mục hình ảnh",
    "danh mục bảng",
    "danh mục từ viết tắt",
    "lời cam đoan",
    "lời cảm ơn",
    "tài liệu tham khảo",
    "references",
    "bibliography",
]


class FileProcessService():

    @staticmethod
    def _find_repetitive_headers_footers(pdf_document: pymupdf.Document) -> set:
        """
        Quét các dòng nằm ở mép trên (12% đầu trang) và mép dưới (12% cuối trang)
        của các trang mẫu để tìm Header/Footer lặp lại (kể cả khi có số trang thay đổi).
        """
        total_pages = len(pdf_document)
        if total_pages <= 3:
            return set()

        line_counts = Counter()
        sample_pages = sorted(list(set(
            list(range(min(10, total_pages))) +
            list(range(max(0, total_pages - 10), total_pages))
        )))

        for p_idx in sample_pages:
            page = pdf_document[p_idx]
            page_height = page.rect.height
            # blocks trả về list các tuple: (x0, y0, x1, y1, "text", block_no, block_type)
            blocks = page.get_text("blocks")

            margin_lines = set()
            for b in blocks:
                y0, y1, block_text, b_type = b[1], b[3], b[4], b[6]
                if b_type == 0:  # Chỉ xét text block (b_type == 0)
                    # Kiểm tra nếu block nằm ở 12% đỉnh trang hoặc 12% đáy trang
                    if y0 < page_height * 0.12 or y1 > page_height * 0.88:
                        for line in block_text.split('\n'):
                            clean_l = unicodedata.normalize("NFC", line.strip())
                            # Chuẩn hóa chữ số thành <NUM> để bắt được dạng "Trang 1", "Trang 2", "1/20"
                            normalized_l = re.sub(r'\b\d+\b', '<NUM>', clean_l)
                            if len(clean_l) > 3:
                                margin_lines.add(normalized_l)

            line_counts.update(margin_lines)

        # Xuất hiện ở >= 45% số trang khảo sát thì đưa vào danh sách đen
        threshold = max(2, int(len(sample_pages) * 0.45))
        headers_footers = {line for line, count in line_counts.items() if count >= threshold}

        if headers_footers:
            print(f"Detected Headers/Footers patterns to remove: {headers_footers}")
        return headers_footers

    @staticmethod
    def _clean_text(text: str, headers_footers_blacklist: set) -> str:
        """
        Làm sạch và chuẩn hóa văn bản tiếng Việt/Anh sau khi trích xuất.
        """
        if not text:
            return ""

        # 1. Chuẩn hóa Unicode về dựng sẵn (NFC) - Rất quan trọng cho Tiếng Việt
        text = unicodedata.normalize("NFC", text)

        # 2. Thay thế các ký tự bullet dị biệt từ PDF (Wingdings/Symbol) thành dấu '-' chuẩn
        text = re.sub(r'[•▪➢\uf0b7\uf0a7\uf076\uf0d8\uf0fc]', '-', text)

        # 3. Chuẩn hóa các ký tự ghép (ligatures) tiếng Anh phổ biến
        text = (
            text.replace("ﬁ", "fi")
            .replace("ﬂ", "fl")
            .replace("ﬀ", "ff")
            .replace("ﬃ", "ffi")
            .replace("ﬄ", "ffl")
        )

        # 4. Loại bỏ control characters và vùng Private Use Area còn sót
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\uE000-\uF8FF]', '', text)

        # 5. Ghép nối từ tiếng Anh bị ngắt dòng bằng dấu gạch ngang (Hyphenation fix)
        text = re.sub(r'([a-zA-Z]+)-\s*\n\s*([a-zA-Z]+)', r'\1\2', text)

        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Kiểm tra với Header/Footer blacklist (đã chuẩn hóa số thành <NUM>)
            normalized_line = re.sub(r'\b\d+\b', '<NUM>', line)
            if (normalized_line in headers_footers_blacklist) or (any(keyword in normalized_line for keyword in headers_footers_blacklist)):
                continue

            # Bỏ các dòng chỉ chứa số trang đơn lẻ (VD: "12", "Trang 12", "Page 5 of 20", "- 5 -")
            if re.match(r'^[-–—\s]*(trang|page)?\s*\d+(\s*(/|of)\s*\d+)?[-–—\s]*$', line.lower()):
                continue

            # Bỏ dòng quá ngắn chỉ toàn chữ số
            if len(line) < 4 and line.isdigit():
                continue

            cleaned_lines.append(line)

        # Gom các khoảng trắng thừa trên cùng 1 dòng
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'[ \t]{2,}', ' ', result)
        return result

    @staticmethod
    def _extract_text_and_tables(page: pymupdf.Page, headers_footers_blacklist: set) -> tuple[str, list[pymupdf.Rect]]:
        """
        Trích xuất văn bản và bảng biểu (dạng Markdown) mà không làm lặp lại nội dung chữ trong bảng.
        Trả về: (chuỗi_văn_bản_đã_gộp_bảng, danh_sách_tọa_độ_các_bảng)
        """
        table_rects: list[pymupdf.Rect] = []
        md_tables: list[str] = []

        # 1. Tìm các bảng biểu native trên trang
        try:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for i, tab in enumerate(tabs.tables):
                    # Chỉ lấy bảng có ít nhất 2 hàng và 2 cột thực sự
                    if tab.row_count >= 2 and tab.col_count >= 2:
                        md_str = tab.to_markdown()
                        if md_str and len(md_str.strip()) > 15:
                            table_rects.append(pymupdf.Rect(tab.bbox))
                            md_tables.append(f"[Bảng dữ liệu {i + 1}]\n{md_str.strip()}")
        except Exception as e:
            print(f"Warning: Table extraction failed on page {page.number + 1}: {e}")

        # 2. Nếu không có bảng, lấy text toàn trang như bình thường
        if not table_rects:
            raw_text = page.get_text("text", sort=True).strip()
            cleaned_text = FileProcessService._clean_text(raw_text, headers_footers_blacklist)
            return cleaned_text, []

        # 3. Nếu có bảng, lọc bỏ các text block nằm bên trong vùng bảng để tránh lặp chữ
        blocks = page.get_text("blocks", sort=True)
        non_table_lines = []
        for b in blocks:
            if b[6] != 0:  # Chỉ lấy text block
                continue
            block_rect = pymupdf.Rect(b[:4])
            # Kiểm tra xem tâm của text block có nằm trong bảng nào không
            center_point = pymupdf.Point(
                (block_rect.x0 + block_rect.x1) / 2,
                (block_rect.y0 + block_rect.y1) / 2
            )
            if any( center_point in t_rect for t_rect in table_rects ):
                continue
            non_table_lines.append(b[4].strip())

        raw_non_table_text = "\n".join(non_table_lines)
        cleaned_text = FileProcessService._clean_text(raw_non_table_text, headers_footers_blacklist)

        # Gộp text thông thường và bảng Markdown
        tables_joined = "\n\n".join(md_tables)
        final_text = f"{cleaned_text}\n\n{tables_joined}".strip()
        return final_text, table_rects

    @staticmethod
    def _has_meaningful_visuals(
        page: pymupdf.Page,
        table_rects: list[pymupdf.Rect],
        min_width: int = 110,
        min_height: int = 110
    ) -> bool:
        """
        Kiểm tra xem trang có chứa:
        1. Ảnh chụp/biểu đồ dạng Raster (PNG/JPG) đủ lớn.
        2. Hoặc Sơ đồ khối (Flowchart/Diagram) vẽ bằng Vector Shapes (ngoài vùng bảng biểu).
        """
        page_area = page.rect.width * page.rect.height

        # 1. Kiểm tra ảnh Raster (bỏ qua icon/logo nhỏ và ảnh nền tràn viền 100% trang)
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            for rect in page.get_image_rects(xref):
                rect_area = rect.width * rect.height
                # Đủ lớn (> 110x110pt) nhưng không phải là background template phủ kín > 92% diện tích slide
                if rect.width >= min_width and rect.height >= min_height:
                    if rect_area < page_area * 0.92:
                        return True
                    # Nếu chỉ có duy nhất 1 ảnh phủ kín trang (VD: trang PDF scan), vẫn phải đọc bằng Vision
                    if len(page.get_text("text").strip()) < 50:
                        return True

        # 2. Kiểm tra hình vẽ Vector (Flowchart/Diagram vẽ bằng Shapes trong PowerPoint/LaTeX)
        drawings = page.get_drawings()
        if len(drawings) > 25:
            page_h = page.rect.height
            non_table_drawings = 0
            for d in drawings:
                d_rect = d.get("rect")
                if not d_rect:
                    continue
                # Bỏ qua các nét trang trí ở sát mép Header/Footer (10% đầu/cuối trang)
                if d_rect.y1 < page_h * 0.10 or d_rect.y0 > page_h * 0.90:
                    continue
                # Bỏ qua các đường kẻ thuộc về bảng biểu đã trích xuất
                if any(d_rect.intersects(t_rect) for t_rect in table_rects):
                    continue
                non_table_drawings += 1

            # Một sơ đồ khối/biểu đồ vector thực sự thường có > 25 hình khối/nét vẽ độc lập
            if non_table_drawings > 25:
                return True

        return False

    @staticmethod
    def _is_garbage_page(
        text: str,
        page_num: int,
        total_pages: int,
        is_slide: bool,
        has_meaningful_visuals: bool
    ) -> bool:
        """
        Phát hiện trang mục lục, tài liệu tham khảo hoặc trang trống không có giá trị cho RAG.
        """
        # Nếu trang có hình ảnh/sơ đồ lớn, KHÔNG đánh dấu là trang rác dù ít chữ
        min_text_len = 25 if is_slide else 40
        if len(text) < min_text_len and not has_meaningful_visuals:
            print(f"Garbage page detected at page {page_num}. Cause: len(text) < {min_text_len} and no visuals.")
            return True

        # Kiểm tra dấu chấm mục lục (". . . . 15" hoặc "..... 15")
        dot_leader_lines = re.findall(r'(\.\s*){4,}\d+', text)
        if len(dot_leader_lines) >= 4:
            print(f"Garbage page detected at page {page_num}. Cause: TOC dot leaders.")
            return True

        # Kiểm tra tiêu đề trang Mục lục / Tài liệu tham khảo dựa trên 3 dòng đầu tiên của trang
        text_lower = text.lower()
        first_lines = "\n".join(text_lower.split('\n')[:3])
        if page_num < 14 or page_num > total_pages - 6:
            if any(re.search(rf'\b{re.escape(kw)}\b', first_lines) for kw in GARBAGE_PAGE_TITLES):
                print(f"Garbage page detected at page {page_num}. Cause: Garbage title keyword in header.")
                return True

        return False

    @staticmethod
    async def _process_pdf(file_path: str, metadata: dict) -> list[Document]:
        """
        Xử lý PDF thông minh: Trích xuất Text + Bảng Markdown + Vision LLM cho Slide/Hình ảnh/Sơ đồ.
        """
        docs = []
        try:
            with pymupdf.open(file_path) as pdf_document:
                total_pages = len(pdf_document)
                print(f"--- Processing PDF: {file_path} ({total_pages} pages) ---")

                headers_footers_blacklist = FileProcessService._find_repetitive_headers_footers(pdf_document)
                total_pages_with_visuals = 0
                visual_content_error = False

                for page_num in range(total_pages):
                    page = pdf_document.load_page(page_num)
                    
                    # Nhận diện trang là Slide (khổ ngang) hay Giáo trình (khổ dọc)
                    is_slide = page.rect.width > page.rect.height

                    # Chỉ bỏ qua trang bìa (page_num == 0) nếu đây là Giáo trình khổ dọc dài (> 15 trang)
                    # Giữ lại trang 1 nếu là Slide bài giảng hoặc tài liệu ngắn vì thường chứa tên chủ đề chính
                    if page_num == 0 and (not is_slide) and total_pages > 15:
                        print("Page 1: Skipped cover page of long textbook.")
                        continue

                    # 1. Trích xuất văn bản sạch và bảng biểu Markdown
                    text, table_rects = FileProcessService._extract_text_and_tables(
                        page, headers_footers_blacklist
                    )

                    # 2. Kiểm tra sự tồn tại của hình ảnh/sơ đồ có ý nghĩa
                    has_visuals = FileProcessService._has_meaningful_visuals(page, table_rects)

                    if not text and not has_visuals:
                        print(f"Page {page_num + 1}: Empty text and no meaningful visuals -> Skip.")
                        continue

                    # 3. Lọc trang rác (Mục lục, Tài liệu tham khảo,...)
                    if FileProcessService._is_garbage_page(
                        text, page_num + 1, total_pages, is_slide, has_visuals
                    ):
                        print(f"Page {page_num + 1}: Identified as garbage page -> Skip.")
                        continue

                    # 4. Xử lý hình ảnh / sơ đồ bằng Vision LLM
                    if has_visuals and not visual_content_error:
                        print(f"Page {page_num + 1}: Meaningful visual content detected. Calling Vision LLM...")
                        total_pages_with_visuals += 1

                        # Render trang ở độ phân giải 2x để đọc rõ chữ nhỏ trong sơ đồ
                        mat = pymupdf.Matrix(2.0, 2.0)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img_data = pix.tobytes("png")

                        with Image.open(io.BytesIO(img_data)) as image:
                            description = await VisionProcessService.describe_image(image)

                        if description == "error":
                            print(f"Page {page_num + 1}: Vision LLM encountered an error -> Skip Vision step for remaining pages.")
                            visual_content_error = True
                        elif description:
                            print(f"Page {page_num + 1}: Vision LLM extracted useful visual context.")
                            text = f"{text}\n\n[Nội dung phân tích từ Hình ảnh/Sơ đồ]\n{description}".strip()
                        else:
                            print(f"Page {page_num + 1}: Visual content is decorative only (SKIP_IMAGE) -> Ignored.")

                    # Kiểm tra độ dài tối thiểu lần cuối sau khi đã gộp cả Text + Table + Vision
                    if len(text) < 20:
                        print(f"Page {page_num + 1}: Final content too short (< 20 chars) -> Skip.")
                        continue

                    # 5. Đóng gói LangChain Document
                    doc = Document(
                        page_content=text,
                        metadata={
                            "filename": metadata.get("filename", ""),
                            "page": page_num + 1,
                            "fileurl": metadata.get("fileurl", ""),
                            "course_name": metadata.get("course_name", "")
                        }
                    )
                    docs.append(doc)

                print(f"--- Finished PDF: {len(docs)}/{total_pages} valid pages extracted (Vision LLM calls: {total_pages_with_visuals}) ---")
                return docs

        except Exception as e:
            print(f"Error processing PDF {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    async def process_file(file_path: str, metadata: dict) -> list[Document]:
        mimetype = metadata.get("mimetype", "")
        if mimetype == "application/pdf":
            return await FileProcessService._process_pdf(file_path, metadata)

        return []