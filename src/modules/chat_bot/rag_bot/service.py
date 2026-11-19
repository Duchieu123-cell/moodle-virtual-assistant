from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from src.modules.chat_bot.rag_bot.schemas import ChosenDocuments
from src.modules.chat_bot.rag_bot.query_refiner import QueryRefiner
from src.modules.chat_bot.rag_bot.prompt import (
    PROMPT_RAG, 
    PROMPT_CHOOSE_DOCS
)
from src.modules.vector_database.vector_db import VectorDatabaseSingleton
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from src.core.config import settings
from src.modules.chat_bot.schemas import (
    ChatTurn,
    format_chat_history
)

GROQ_API_KEY = settings.GROQ_API_KEY

class RagService():
    vector_db = VectorDatabaseSingleton.get()
    
    @staticmethod
    async def retrieve(message: str) -> tuple[str | None, list[dict]]:
        """
        Tìm kiếm tài liệu và format thành context.
        Trả về (None, []) nếu không tìm thấy tài liệu phù hợp.
        """
        print(f"--- RAG Retrieval Start: '{message}' ---")
        # Lọc nhiễu & Trích xuất trọng tâm cho cả query trước khi search để tăng hiệu quả tìm kiếm
        refined_query = await QueryRefiner.refine(message)
        translated_refined_query = await QueryRefiner.translate(refined_query)
        print(f"--- Refined Query: {refined_query} ---")
        print(f"--- Refined Translated Query: {translated_refined_query} ---")
        
        # 1. Gọi hàm search với rerank (kết quả đã được lọc theo threshold bên vectorDB)
        # Tham số k là số lượng tối đa, nếu threshold lọc bớt thì có thể trả về ít hơn
        retrieved_docs_for_refined = await RagService.vector_db.search_with_rerank(
            query=refined_query,
            k_return=3,
            k_search=15,
            threshold=0.8
        )

        retrieved_docs_for_translated_refined = await RagService.vector_db.search_with_rerank(
            query=translated_refined_query,
            k_return=3,
            k_search=15,
            threshold=0.8
        )
        
        retrieved_docs = []
        retrieved_docs.extend(retrieved_docs_for_refined)
        retrieved_docs.extend(retrieved_docs_for_translated_refined)
        
        # 2. Kiểm tra danh sách rỗng (Empty List Check)
        # Trường hợp này xảy ra khi không có doc nào vượt qua ngưỡng threshold
        if not retrieved_docs or len(retrieved_docs) == 0:
            print("No documents passed the relevance threshold.")
            return None, []

        if len(retrieved_docs) > 0:
            context = ""
            for i, doc in enumerate(retrieved_docs):
                filename = doc.metadata.get('filename')
                context += f"--- (ID: {i}, Source: {filename}) ---\n"
                context += f"{doc.page_content}\n\n"
            
            # 2.1. Chọn lọc tài liệu phù hợp nhất bằng prompt chuyên dụng
            chain = (
                PROMPT_CHOOSE_DOCS |
                ChatGroq(
                    model_name="openai/gpt-oss-120b",
                    temperature=0.2,
                    groq_api_key=GROQ_API_KEY
                ).with_structured_output(ChosenDocuments, method="json_mode")
            )
            response = await chain.ainvoke({ "input": message, "documents": context})
            chosen_ids = response.list_ids if response and response.list_ids else []
            if not chosen_ids:
                print("No documents were chosen by the LLM.")
                return None, []
            
            print(f"Chosen document IDs: {chosen_ids}")
            
            # 2.2. Lọc lại retrieved_docs chỉ giữ những doc có ID trong chosen_ids
            retrieved_docs = [retrieved_docs[i.id] for i in chosen_ids if i.id < len(retrieved_docs)]
        
            # Trường hợp này xảy ra khi không có doc nào lọc ra sau bước chọn lọc bằng prompt
            if not retrieved_docs or len(retrieved_docs) == 0:
                print("No documents passed the relevance threshold.")
                return None, []
        
        # 3. Xử lý tài liệu để tạo context trả về
        context = ""
        fileinfos = []
        for i, doc in enumerate(retrieved_docs):
            filename: str = doc.metadata.get('filename')
            page = int(doc.metadata.get("page"))
            
            # Format context rõ ràng hơn để LLM dễ đọc
            context += f"--- Doc {i+1}: {filename}, page: {page} ---\nContent: {doc.page_content}\n\n"

            fileinfo = {
                "filename": filename,
                "fileurl": doc.metadata.get("fileurl"),
                "pagenumber": page
            }
            
            # Tránh trùng lặp file info hiển thị cho user
            if fileinfo not in fileinfos:
                fileinfos.append(fileinfo)

        # In ra để tiện debug
        print("-"*60)
        print(f"CONTEXT FOUND ({len(retrieved_docs)} docs):\n{context}...")
        print("-"*60)
        
        return context, fileinfos
    
    # Hàm thực hiện Web Search trả về cả URL
    @staticmethod
    async def web_search_fallback(query: str, max_results: int = 3) -> list:
        """
        Thực hiện tìm kiếm trên internet và trả về danh sách kết quả chứa URL.
        Output format: [{'title': '...', 'link': '...', 'snippet': '...'}]
        """
        try:
            print(f"LOG: Triggering DuckDuckGo Search for: '{query}'...")
            # Sử dụng Wrapper để lấy cấu trúc dữ liệu thô (Raw Data)
            wrapper = DuckDuckGoSearchAPIWrapper(max_results=max_results)
            results = wrapper.results(query, max_results)
            return results
        except Exception as e:
            print(f"Web search error: {e}")
            return []
    
    @staticmethod
    async def rag(message: str, chat_history: list[ChatTurn]):
        # 1. Gọi hàm retrieve
        context, fileinfos = await RagService.retrieve(message)
        websearchinfos = []  # Khởi tạo danh sách websearchinfos để trả về cho Frontend, sẽ chứa dict với 'title' và 'url'
        
        # 2. Xử lý trường hợp context rỗng
        if not context:
            print("Current knowledge base is empty for this query. Falling back to Web Search...")
            
            # Khai thác QueryRefiner một lần nữa để lấy keyword search web cho chuẩn
            search_keyword = await QueryRefiner.refine(message)
            web_results = await RagService.web_search_fallback(search_keyword)

            # Kiểm tra nếu web_results bị rỗng (mất mạng hoặc không có kết quả)
            if not web_results:
                print("Web search không cho kết quả.")
                return "Xin lỗi, tôi không tìm thấy thông tin trong cơ sở dữ liệu và cả trên Internet để trả lời bạn.", []
            
            # Khởi tạo lại context vào websearchinfos cho Web
            context = ""
            
            # Lặp qua từng kết quả web để bóc tách Tiêu đề, Snippet và URL
            for i, res in enumerate(web_results):
                title = res.get('title', 'Unknown Title')
                url = res.get('link', 'Unknown Link')
                snippet = res.get('snippet', '')
                
                # Đưa snippet vào context để LLM đọc
                context += f"--- Web Source {i+1}: {title} ---\nContent: {snippet}\n\n"
                
                # Đưa Title và URL vào websearchinfos để trả về cho Frontend hiển thị
                websearchinfo = {
                    "title": title,
                    "url": url
                }
                
                if websearchinfo not in websearchinfos:
                    websearchinfos.append(websearchinfo)
            
            print("-"*60)
            print(f"WEB CONTEXT FOUND ({len(web_results)} results):\n{context}...")
            print("-"*60)

        # 3. Nếu có Context (từ Local DB hoặc Web), gọi LLM sinh câu trả lời
        try:
            chain = (
                PROMPT_RAG | 
                ChatGroq(
                    model_name="openai/gpt-oss-20b",
                    temperature=0.4,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            response = await chain.ainvoke({
                "chat_history": format_chat_history(chat_history),
                "context": context,
                "input": message
            })
            
            print("-"*60)
            print("Rag response:\n", response)
            print("-"*60)
                 
            return {
                "response": response,
                "fileinfos": fileinfos,
                "websearchinfos": websearchinfos,
                "type": "rag_response"
            }
            
        except Exception as e:
            print(f"Error occurred while calling LLM: {e}")
            return "Xin lỗi, hệ thống đang gặp sự cố khi xử lý câu trả lời. Vui lòng thử lại sau.", []