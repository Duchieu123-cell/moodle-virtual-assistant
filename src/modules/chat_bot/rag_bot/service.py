from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import asyncio
import re

from ddgs import DDGS
import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from lxml import html as lxml_html
from tavily import AsyncTavilyClient

from src.core.config import settings
from src.modules.chat_bot.rag_bot.prompt import (
    PROMPT_CHOOSE_DOCS,
    PROMPT_RAG,
)
from src.modules.chat_bot.rag_bot.query_refiner import QueryRefiner
from src.modules.chat_bot.rag_bot.schemas import ChosenDocuments, Doc
from src.modules.chat_bot.schemas import (
    ChatTurn,
    format_chat_history,
)
from src.modules.vector_database.vector_db import VectorDatabaseSingleton
import logging

logger = logging.getLogger(__name__)

GROQ_API_KEY = settings.GROQ_API_KEY

# Giới hạn độ dài cột CHAR(255) của bảng mdl_local_mychatbot_rag_web_references trong Moodle
MOODLE_WEB_REF_MAX_LEN = 255
TAVILY_MIN_SCORE = 0.35
WEB_FETCH_TIMEOUT_SEC = 4.0
WEB_EXCERPT_MAX_CHARS = 1500
_TRACKING_QUERY_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref"}


def _clamp_text(text: str, max_len: int) -> str:
    """Chuẩn hóa khoảng trắng và cắt gọn văn bản theo giới hạn độ dài."""
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3].rstrip() + "..."


def _clean_url_for_moodle(url: str, max_len: int = MOODLE_WEB_REF_MAX_LEN) -> str | None:
    """Làm sạch tham số tracking và đảm bảo URL nằm trong giới hạn CHAR(255) của Moodle."""
    raw = (url or "").strip()
    if not raw:
        return None

    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None

    if len(raw) <= max_len:
        return raw

    filtered_query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_QUERY_PARAMS
    ]
    cleaned = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(filtered_query), "")
    )
    return cleaned if len(cleaned) <= max_len else None


def _normalize_web_results(raw_results: list[dict], max_results: int) -> list[dict]:
    """Khử trùng lặp theo URL, lọc kết quả rỗng và chuẩn hóa format cho Moodle/RAG."""
    normalized = []
    seen_urls = set()

    for item in raw_results:
        raw_url = item.get("link") or item.get("url") or item.get("href") or ""
        clean_url = _clean_url_for_moodle(raw_url)
        if not clean_url:
            continue

        dedup_key = clean_url.split("#")[0].rstrip("/").lower()
        if dedup_key in seen_urls:
            continue

        title = _clamp_text(item.get("title") or clean_url, MOODLE_WEB_REF_MAX_LEN)
        snippet = re.sub(
            r"\s+",
            " ",
            (item.get("snippet") or item.get("content") or item.get("body") or ""),
        ).strip()
        if not snippet:
            continue

        seen_urls.add(dedup_key)
        normalized.append(
            {
                "title": title,
                "link": clean_url,
                "snippet": snippet,
            }
        )
        if len(normalized) >= max_results:
            break

    return normalized


class RagService:
    vector_db = VectorDatabaseSingleton.get()

    @staticmethod
    async def retrieve(message: str) -> tuple[str | None, list[dict], str]:
        """
        Tìm kiếm tài liệu và format thành context.
        Trả về (None, [], refined_query) nếu không tìm thấy tài liệu phù hợp.
        """
        logger.info("Start RAG retrieval for message: '%s'", message)
        # Lọc nhiễu & Trích xuất trọng tâm cho cả query trước khi search để tăng hiệu quả tìm kiếm
        refined_query = await QueryRefiner.refine(message)
        logger.info("Refined query: '%s'", refined_query)
        
        translated_refined_query = await QueryRefiner.translate(refined_query)
        logger.info("Translated refined query: '%s'", translated_refined_query)

        # 1. Gọi song song search_with_rerank cho câu gốc đã tinh chỉnh và bản dịch song ngữ
        retrieved_docs_for_refined, retrieved_docs_for_translated_refined = await asyncio.gather(
            RagService.vector_db.search_with_rerank(
                query=refined_query,
                k_return=3,
                k_search=15,
                threshold=0.8,
            ),
            RagService.vector_db.search_with_rerank(
                query=translated_refined_query,
                k_return=3,
                k_search=15,
                threshold=0.8,
            ),
        )

        # Khử trùng lặp theo nội dung khi gộp kết quả từ 2 truy vấn song ngữ
        seen_contents = set()
        retrieved_docs = []
        for doc in (*retrieved_docs_for_refined, *retrieved_docs_for_translated_refined):
            if doc.page_content not in seen_contents:
                seen_contents.add(doc.page_content)
                retrieved_docs.append(doc)

        # 2. Kiểm tra danh sách rỗng (Empty List Check)
        # Trường hợp này xảy ra khi không có doc nào vượt qua ngưỡng threshold
        if not retrieved_docs:
            logger.info("No documents passed the relevance threshold")
            return None, [], refined_query

        context = ""
        for i, doc in enumerate(retrieved_docs):
            filename = doc.metadata.get("filename")
            context += f"--- (ID: {i}, Source: {filename}) ---\n"
            context += f"{doc.page_content}\n\n"

        # 2.1. Chọn lọc tài liệu phù hợp nhất bằng prompt chuyên dụng
        chain = (
            PROMPT_CHOOSE_DOCS
            | ChatGroq(
                model_name="openai/gpt-oss-120b",
                temperature=0.2,
                groq_api_key=GROQ_API_KEY,
            ).with_structured_output(ChosenDocuments, method="json_mode")
        )
        response: ChosenDocuments = await chain.ainvoke({"input": message, "documents": context})
        chosen_ids: list[Doc] = response.list_ids if response and response.list_ids else []
        if not chosen_ids:
            logger.info("No documents were chosen by the LLM")
            return None, [], refined_query

        logger.info("Chosen document IDs: %s", chosen_ids)

        # 2.2. Lọc lại retrieved_docs chỉ giữ những doc có ID trong chosen_ids
        retrieved_docs = [
            retrieved_docs[i.id] for i in chosen_ids if i.id < len(retrieved_docs)
        ]

        # Trường hợp này xảy ra khi không có doc nào lọc ra sau bước chọn lọc bằng prompt
        if not retrieved_docs:
            logger.info("No documents passed the relevance threshold")
            return None, [], refined_query

        logger.info("Retrieved %d documents after filtering by chosen IDs", len(retrieved_docs))
        # 3. Xử lý tài liệu để tạo context trả về
        context = ""
        fileinfos = []
        for i, doc in enumerate(retrieved_docs):
            filename: str = doc.metadata.get("filename")
            page = int(doc.metadata.get("page"))

            # Format context rõ ràng hơn để LLM dễ đọc
            context += (
                f"--- Doc {i+1}: {filename}, page: {page} ---\n"
                f"Content: {doc.page_content}\n\n"
            )

            fileinfo = {
                "filename": filename,
                "fileurl": doc.metadata.get("fileurl"),
                "pagenumber": page,
            }

            # Tránh trùng lặp file info hiển thị cho user
            if fileinfo not in fileinfos:
                fileinfos.append(fileinfo)

        logger.debug("Final context for RAG:\n%s", context)
        
        return context, fileinfos, refined_query

    @staticmethod
    async def _tavily_search(query: str, max_results: int) -> list[dict]:
        """Tầng 1: Truy vấn Tavily Async API và lọc kết quả theo độ liên quan."""
        if not settings.TAVILY_API_KEY:
            return []

        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        payload = await client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_raw_content=False,
            timeout=15.0,
        )
        raw_items = payload.get("results", []) if isinstance(payload, dict) else []
        filtered = []
        for item in raw_items:
            score = item.get("score")
            if score is not None and float(score) < TAVILY_MIN_SCORE:
                continue
            filtered.append(
                {
                    "title": item.get("title", ""),
                    "link": item.get("url", ""),
                    "snippet": item.get("content", ""),
                }
            )
        return _normalize_web_results(filtered, max_results)

    @staticmethod
    async def _extract_page_excerpt(
        client: httpx.AsyncClient,
        url: str,
        max_chars: int = WEB_EXCERPT_MAX_CHARS,
    ) -> str:
        """Tải trang HTML bất đồng bộ và trích xuất văn bản chính sạch nhiễu."""
        try:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return ""
            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return ""

            doc = lxml_html.fromstring(resp.text)
            for tag in doc.xpath("//script|//style|//noscript|//nav|//footer|//header|//aside"):
                parent = tag.getparent()
                if parent is not None:
                    parent.remove(tag)

            main_nodes = doc.xpath("//article | //main")
            target = main_nodes[0] if main_nodes else doc
            paragraphs = [
                re.sub(r"\s+", " ", p.text_content()).strip()
                for p in target.xpath(".//p | .//li")
            ]
            meaningful = [p for p in paragraphs if len(p) >= 30]
            if not meaningful:
                return ""
            return _clamp_text(" ".join(meaningful), max_chars)
        except Exception:
            return ""

    @staticmethod
    async def _ddgs_fallback_search(query: str, max_results: int) -> list[dict]:
        """Tầng 2: Tìm kiếm DDGS trên worker thread và làm giàu nội dung bằng httpx/lxml."""
        def _run_ddgs() -> list[dict]:
            return DDGS(timeout=6).text(
                query,
                region="wt-wt",
                safesearch="moderate",
                max_results=max_results,
            )

        raw_items = await asyncio.to_thread(_run_ddgs)
        if not raw_items:
            return []

        base_results = _normalize_web_results(raw_items, max_results)
        if not base_results:
            return []

        async with httpx.AsyncClient(
            timeout=WEB_FETCH_TIMEOUT_SEC,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MoodleRAGBot/1.0)"},
        ) as client:
            excerpts = await asyncio.gather(
                *[RagService._extract_page_excerpt(client, r["link"]) for r in base_results]
            )

        for result, excerpt in zip(base_results, excerpts):
            if len(excerpt) > len(result["snippet"]):
                result["snippet"] = excerpt

        return base_results

    @staticmethod
    async def web_search_fallback(query: str, max_results: int = 3) -> list[dict]:
        """
        Thực hiện tìm kiếm web bất đồng bộ theo 2 tầng (Tavily -> DDGS + trích xuất HTML).
        Output format: [{'title': '...', 'link': '...', 'snippet': '...'}]
        """
        clean_query = (query or "").strip()
        if not clean_query or max_results <= 0:
            return []

        if settings.TAVILY_API_KEY:
            try:
                logger.info("Triggering Tavily Async Search for: '%s'", clean_query)
                tavily_results = await RagService._tavily_search(clean_query, max_results)
                if tavily_results:
                    return tavily_results
                logger.info("Tavily returned no qualified results. Falling back to DDGS...")
            except Exception as e:
                logger.exception("Tavily search error: %s. Falling back to DDGS...", str(e))

        try:
            logger.info("Triggering Async DDGS Fallback Search for: '%s'", clean_query)
            return await RagService._ddgs_fallback_search(clean_query, max_results)
        except Exception as e:
            logger.exception("DDGS fallback search error: %s", str(e))
            return []

    @staticmethod
    async def rag(message: str, chat_history: list[ChatTurn]):
        # 1. Gọi hàm retrieve
        context, fileinfos, refined_query = await RagService.retrieve(message)
        websearchinfos = []

        # 2. Xử lý trường hợp context rỗng -> Fallback sang Web Search
        if not context:
            logger.info("Current knowledge base is empty for this query. Falling back to Web Search...")

            search_keyword = await QueryRefiner.rewrite_for_web(
                message,
                chat_history,
                fallback_query=refined_query,
            )
            web_results = await RagService.web_search_fallback(search_keyword)
            logger.info("Web search results: %d", len(web_results))

            if not web_results:
                logger.info("Web search returned no results. Returning default response.")
                return {
                    "response": "<p>Xin lỗi, tôi không tìm thấy thông tin trong cơ sở dữ liệu và cả trên Internet để trả lời bạn.</p>",
                    "fileinfos": [],
                    "websearchinfos": [],
                    "type": "rag_response",
                }

            context = ""
            seen_urls = set()
            for i, res in enumerate(web_results):
                title = res.get("title", "Unknown Title")
                url = res.get("link", "")
                snippet = res.get("snippet", "")

                context += f"--- Web Source {i+1}: {title} ---\nContent: {snippet}\n\n"

                if url and url not in seen_urls:
                    seen_urls.add(url)
                    websearchinfos.append({"title": title, "url": url})

            
            logger.info("Web search context prepared with %d sources", len(websearchinfos))
            logger.debug("Web search context:\n%s", context)

        # 3. Nếu có Context (từ Local DB hoặc Web), gọi LLM sinh câu trả lời
        try:
            chain = (
                PROMPT_RAG
                | ChatGroq(
                    model_name="openai/gpt-oss-20b",
                    temperature=0.4,
                    groq_api_key=GROQ_API_KEY,
                )
                | StrOutputParser()
            )
            response = await chain.ainvoke(
                {
                    "chat_history": format_chat_history(chat_history),
                    "context": context,
                    "input": message,
                }
            )
            
            logger.info("RAG response generated successfully")
            logger.debug("RAG response:\n%s", response)

            return {
                "response": response,
                "fileinfos": fileinfos,
                "websearchinfos": websearchinfos,
                "type": "rag_response",
            }

        except Exception as e:
            logger.exception("Failed to generate RAG response: %s", str(e))
            return {
                "response": "<p>Xin lỗi, hệ thống đang gặp sự cố khi xử lý câu trả lời. Vui lòng thử lại sau.</p>",
                "fileinfos": [],
                "websearchinfos": [],
                "type": "rag_response",
            }
