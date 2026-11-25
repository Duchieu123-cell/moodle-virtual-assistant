import asyncio
import logging
import re
import uuid

from elasticsearch import AsyncElasticsearch, helpers
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
import numpy as np
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import CrossEncoder
from torch import nn

from src.core.config import settings
from src.modules.file_processor.service import FileProcessService
from src.modules.vector_database.synonyms import synonym_list

logger = logging.getLogger(__name__)

PINECONE_API_KEY = settings.PINECONE_API_KEY
ES_URL = settings.ES_URL
ES_INDEX_NAME = PINECONE_INDEX_NAME = "moodle-files"


# ===============================================================
# CLASS CUSTOM RETRIEVER CHO ELASTICSEARCH (BM25 + FILTER/BOOST)
# ===============================================================
class ElasticsearchBM25Retriever(BaseRetriever):
    """
    Custom Retriever thực hiện tìm kiếm BM25 trực tiếp trên Elasticsearch,
    hỗ trợ lọc cứng (strict_filter) hoặc ưu tiên (boost) theo metadata.
    """

    client: AsyncElasticsearch
    index_name: str
    k: int
    target_course: str | None = None
    metadata_filters: dict | None = None
    strict_filter: bool = False

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> list[Document]:
        raise NotImplementedError("Use ainvoke instead for async support")

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> list[Document]:
        filter_clauses = []
        should_clauses = []

        if self.metadata_filters:
            for key, value in self.metadata_filters.items():
                if value is None:
                    continue
                if self.strict_filter or key != "course_name":
                    filter_clauses.append(
                        {"match_phrase": {f"metadata.{key}": value}}
                    )

        if not self.strict_filter and self.target_course:
            should_clauses.append(
                {
                    "match_phrase": {
                        "metadata.course_name": {
                            "query": self.target_course,
                            "boost": 2.0,
                        }
                    }
                }
            )

        bool_query: dict = {
            "must": [
                {
                    "match": {
                        "text": {
                            "query": query,
                        }
                    }
                }
            ]
        }
        if filter_clauses:
            bool_query["filter"] = filter_clauses
        if should_clauses:
            bool_query["should"] = should_clauses

        try:
            response = await self.client.search(
                index=self.index_name,
                size=self.k,
                query={"bool": bool_query},
            )
        except Exception as e:
            logger.warning("Elasticsearch search skipped (%s): %s", self.index_name, e)
            return []

        documents = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            documents.append(
                Document(
                    page_content=source.get("text", ""),
                    metadata=source.get("metadata", {}),
                )
            )
        return documents


# ===============================================================
# MAIN VECTOR DATABASE CLASS
# ===============================================================
class VectorDatabase:
    def __init__(self):
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self._ensure_pinecone_index()
        self._pinecone_index = self.pc.Index(PINECONE_INDEX_NAME)

        # 1. Model Embedding Đa ngôn ngữ (Hỗ trợ tốt Tiếng Việt + Tiếng Anh, giữ nguyên 768 chiều)
        logger.info("Loading Multilingual Embedding Model...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            encode_kwargs={"normalize_embeddings": True},
        )
        self._pinecone_store = PineconeVectorStore(
            index=self._pinecone_index,
            embedding=self.embedding_model,
        )

        # 2. Khởi tạo Elasticsearch Client
        logger.info("Initializing Elasticsearch client at %s...", ES_URL)
        self.es_client: AsyncElasticsearch | None = None
        if ES_URL:
            try:
                self.es_client = AsyncElasticsearch(
                    hosts=[ES_URL],
                    verify_certs=False,
                    request_timeout=60,
                )
            except Exception as e:
                logger.warning("Failed to initialize Elasticsearch client: %s", e)

        # 3. Khởi tạo Reranker Đa ngôn ngữ với Sigmoid rõ ràng (tránh Double Sigmoid)
        logger.info("Loading Multilingual Rerank Model...")
        self.rerank_model = CrossEncoder(
            "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
            activation_fn=nn.Sigmoid(),
        )

        # 4. Chuẩn bị Dictionary và compile Regex 1 lần cho việc map từ đồng nghĩa
        self.synonym_dict = self._build_synonym_dict(synonym_list)
        self._synonym_pattern: re.Pattern | None = None
        if self.synonym_dict:
            sorted_keys = sorted(self.synonym_dict.keys(), key=len, reverse=True)
            pattern_str = r"(?<!\w)(" + "|".join(map(re.escape, sorted_keys)) + r")(?!\w)"
            self._synonym_pattern = re.compile(pattern_str, re.IGNORECASE)

    async def close(self):
        """Đóng kết nối AsyncElasticsearch khi FastAPI shutdown."""
        if self.es_client is not None:
            try:
                await self.es_client.close()
            except Exception as e:
                logger.warning("Error closing Elasticsearch client: %s", e)

    def _build_synonym_dict(self, raw_synonyms: list[str]) -> dict[str, list[str]]:
        """
        Biến đổi danh sách synonym thành dictionary (hỗ trợ gộp nếu 1 từ xuất hiện ở nhiều dòng).
        """
        syn_dict: dict[str, list[str]] = {}
        for line in raw_synonyms:
            terms = [t.strip().lower() for t in line.split(",") if t.strip()]
            for term in terms:
                existing = syn_dict.setdefault(term, [])
                for other in terms:
                    if other != term and other not in existing:
                        existing.append(other)
        return syn_dict

    def _expand_query_with_synonyms(self, query: str, max_expansion: int = 4) -> list[str]:
        """
        Mở rộng câu truy vấn với từ đồng nghĩa theo vòng tròn (round-robin) trên mọi cụm khớp,
        giới hạn số biến thể tối đa (max_expansion) để tránh nghẽn CPU khi Rerank.
        """
        if not self._synonym_pattern or not self.synonym_dict or max_expansion <= 1:
            return [query]

        tokens = self._synonym_pattern.split(query)
        matched_positions: list[tuple[int, list[str]]] = []
        for idx, token in enumerate(tokens):
            if not token:
                continue
            synonyms = self.synonym_dict.get(token.lower())
            if synonyms:
                matched_positions.append((idx, synonyms))

        if not matched_positions:
            return [query]

        expanded_queries = [query]
        max_syn_depth = max(len(syns) for _, syns in matched_positions)

        # Thay thế công bằng từng cụm khớp theo lượt (round-robin)
        for syn_idx in range(max_syn_depth):
            for pos, syns in matched_positions:
                if syn_idx >= len(syns):
                    continue
                variant_tokens = list(tokens)
                variant_tokens[pos] = syns[syn_idx]
                variant = "".join(variant_tokens)
                if variant not in expanded_queries:
                    expanded_queries.append(variant)
                if len(expanded_queries) >= max_expansion:
                    return expanded_queries

        # Nếu có từ 2 cụm khớp trở lên và còn ngân sách, thêm 1 biến thể thay thế đồng thời
        if len(matched_positions) >= 2 and len(expanded_queries) < max_expansion:
            all_replaced = list(tokens)
            for pos, syns in matched_positions:
                all_replaced[pos] = syns[0]
            combined = "".join(all_replaced)
            if combined not in expanded_queries:
                expanded_queries.append(combined)

        return expanded_queries

    def _ensure_pinecone_index(self):
        """Đảm bảo Index trên Pinecone đã tồn tại (768 dimensions)."""
        try:
            existing_indexes = [i.name for i in self.pc.list_indexes()]
            if PINECONE_INDEX_NAME not in existing_indexes:
                self.pc.create_index(
                    PINECONE_INDEX_NAME,
                    dimension=768,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                logger.info("Pinecone index '%s' đã được tạo.", PINECONE_INDEX_NAME)
        except Exception as e:
            logger.exception("Lỗi khi kiểm tra/tạo index Pinecone: %s", e)
            raise RuntimeError(f"Lỗi khi tạo index Pinecone: {e}") from e

    def _get_pinecone_store(self) -> PineconeVectorStore:
        return self._pinecone_store

    async def _create_es_index_if_not_exists(self):
        """Kiểm tra và tạo Index trong Elasticsearch với cấu hình tiếng Việt."""
        if self.es_client is None:
            return

        if not await self.es_client.indices.exists(index=ES_INDEX_NAME):
            logger.info("Creating ES index '%s' with Vietnamese analyzer...", ES_INDEX_NAME)
            await self.es_client.indices.create(
                index=ES_INDEX_NAME,
                settings={
                    "analysis": {
                        "filter": {
                            "my_synonym_graph": {
                                "type": "synonym_graph",
                                "synonyms": synonym_list,
                                "expand": True,
                            }
                        },
                        "analyzer": {
                            "vi_search_analyzer": {
                                "tokenizer": "vi_tokenizer",
                                "filter": ["lowercase", "my_synonym_graph"],
                            },
                            "vi_index_analyzer": {
                                "tokenizer": "vi_tokenizer",
                                "filter": ["lowercase"],
                            },
                        },
                    }
                },
                mappings={
                    "properties": {
                        "text": {
                            "type": "text",
                            "analyzer": "vi_index_analyzer",
                            "search_analyzer": "vi_search_analyzer",
                        },
                        "metadata": {
                            "properties": {
                                "course_name": {"type": "keyword"},
                                "filename": {"type": "keyword"},
                                "fileurl": {"type": "keyword"},
                                "page": {"type": "integer"},
                                "start_index": {"type": "integer"},
                            }
                        },
                    }
                },
            )

    def _purge_pinecone_prefix_sync(self, doc_prefix: str):
        prefix = f"{doc_prefix}#"
        for id_batch in self._pinecone_index.list(prefix=prefix):
            if id_batch:
                self._pinecone_index.delete(ids=list(id_batch))

    async def _purge_existing_file_chunks(self, doc_prefix: str, use_es: bool):
        """Xóa các chunk cũ của cùng tài liệu trước khi re-index để tránh dữ liệu mồ côi."""
        tasks = [asyncio.to_thread(self._purge_pinecone_prefix_sync, doc_prefix)]
        if use_es and self.es_client is not None:
            if await self.es_client.indices.exists(index=ES_INDEX_NAME):
                tasks.append(
                    self.es_client.delete_by_query(
                        index=ES_INDEX_NAME,
                        query={"prefix": {"_id": f"{doc_prefix}#"}},
                        refresh=True,
                    )
                )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                logger.warning("Failed to purge stale chunks for prefix %s: %s", doc_prefix, res)

    async def add_file_to_index(self, file_path: str, metadata: dict) -> bool:
        """
        Trích xuất nội dung từ file, chia chunk bảo toàn cấu trúc Bảng/Vision,
        xóa chunk cũ (nếu re-index) và lưu đồng bộ vào Pinecone + Elasticsearch.
        """
        try:
            logger.info("Processing file for indexing: %s", file_path)
            # --- BƯỚC 1: TRÍCH XUẤT NỘI DUNG TỪ FILE PROCESS SERVICE ---
            docs = await FileProcessService.process_file(file_path, metadata)
            if not docs:
                logger.info("No valid content extracted from file: %s", file_path)
                return False

            logger.info("Extracted %d valid pages from file.", len(docs))

            # --- BƯỚC 2: CHIA CHUNK BẢO TOÀN BẢNG & MÔ TẢ HÌNH ẢNH ---
            text_splitter = RecursiveCharacterTextSplitter(
                separators=[
                    "\n\n[Nội dung phân tích từ Hình ảnh/Sơ đồ]\n",
                    "\n\n[Bảng dữ liệu",
                    "\n\n",
                    "\n",
                    ". ",
                    " ",
                    "",
                ],
                chunk_size=1200,
                chunk_overlap=200,
                length_function=len,
                add_start_index=True,
            )
            splits = text_splitter.split_documents(docs)
            if not splits:
                return False

            # --- BƯỚC 3: BỔ SUNG NGỮ CẢNH ĐẦU CHUNK & TẠO PREFIX ID TẤT ĐỊNH ---
            base_course = metadata.get("course_name", "")
            base_filename = metadata.get("filename", "")
            base_fileurl = metadata.get("fileurl", "")
            doc_prefix = str(
                uuid.uuid5(uuid.NAMESPACE_DNS, f"{base_course}::{base_filename}::{base_fileurl}")
            )

            chunk_ids = []
            for idx, split in enumerate(splits):
                filename = split.metadata.get("filename", base_filename)
                course_name = split.metadata.get("course_name", base_course)
                page_num = split.metadata.get("page", 1)

                header_ctx = f"[Tài liệu: {filename} | Trang {page_num}]"
                if course_name:
                    header_ctx = f"[Môn: {course_name} | Tài liệu: {filename} | Trang {page_num}]"

                if not split.page_content.startswith("[Môn:") and not split.page_content.startswith(
                    "[Tài liệu:"
                ):
                    split.page_content = f"{header_ctx}\n{split.page_content}"

                chunk_ids.append(f"{doc_prefix}#{idx}")

            logger.info("Split into %d contextualized chunks (prefix=%s).", len(splits), doc_prefix)

            # Kiểm tra kết nối Elasticsearch trước khi ghi để tránh lệch pha 2 kho
            use_es = False
            if self.es_client is not None:
                if not await self.es_client.ping():
                    logger.error("Cannot ping Elasticsearch! Aborting index to avoid dual-store desync.")
                    return False
                await self._create_es_index_if_not_exists()
                use_es = True

            # --- BƯỚC 4: XÓA CHUNK CŨ CỦA FILE NÀY TRƯỚC KHI UPSERT ---
            await self._purge_existing_file_chunks(doc_prefix, use_es)

            # --- BƯỚC 5: UPSERT ĐỒNG THỜI VÀO PINECONE & ELASTICSEARCH ---
            vector_store = self._get_pinecone_store()
            upsert_tasks = [vector_store.aadd_documents(documents=splits, ids=chunk_ids)]

            if use_es and self.es_client is not None:
                actions = [
                    {
                        "_op_type": "index",
                        "_index": ES_INDEX_NAME,
                        "_id": doc_id,
                        "_source": {
                            "text": split.page_content,
                            "metadata": split.metadata,
                        },
                    }
                    for split, doc_id in zip(splits, chunk_ids)
                ]
                upsert_tasks.append(
                    helpers.async_bulk(self.es_client, actions, raise_on_error=False)
                )

            results = await asyncio.gather(*upsert_tasks, return_exceptions=True)

            pinecone_res = results[0]
            if isinstance(pinecone_res, Exception):
                logger.error("Pinecone upsert failed: %s", pinecone_res)
                return False

            if use_es:
                es_res = results[1]
                if isinstance(es_res, Exception):
                    logger.error("Elasticsearch bulk index failed: %s", es_res)
                    return False
                success_count, failed = es_res
                logger.info(
                    "Elasticsearch add result: %d docs indexed, %d failed.",
                    success_count,
                    len(failed),
                )
                if failed:
                    return False

            return True

        except Exception as e:
            logger.exception("Lỗi khi xử lý file %s: %s", file_path, e)
            return False

    def _build_pinecone_search_kwargs(
        self,
        k_search: int,
        metadata_filters: dict | None,
        strict_filter: bool,
    ) -> dict:
        search_kwargs: dict = {"k": k_search}
        if not metadata_filters:
            return search_kwargs

        pinecone_filter = {
            k: v
            for k, v in metadata_filters.items()
            if v is not None and (strict_filter or k != "course_name")
        }
        if pinecone_filter:
            search_kwargs["filter"] = pinecone_filter
        return search_kwargs

    async def search_with_rerank(
        self,
        query: str,
        k_return: int,
        k_search: int,
        threshold: float,
        metadata_filters: dict | None = None,
        strict_filter: bool = False,
    ) -> list[Document]:
        """
        Tìm kiếm Hybrid (Pinecone + Elasticsearch) kết hợp Max-Pooling Cross-Encoder Rerank.
        """
        try:
            logger.info("START SEARCHING: '%s' (strict_filter=%s)", query, strict_filter)
            target_course = metadata_filters.get("course_name") if metadata_filters else None

            # --- BƯỚC 1: RETRIEVAL (Thu thập ứng viên) ---
            vector_store = self._get_pinecone_store()
            pinecone_retriever = vector_store.as_retriever(
                search_kwargs=self._build_pinecone_search_kwargs(
                    k_search, metadata_filters, strict_filter
                )
            )

            if self.es_client is not None and await self.es_client.ping():
                es_retriever = ElasticsearchBM25Retriever(
                    client=self.es_client,
                    index_name=ES_INDEX_NAME,
                    k=k_search,
                    target_course=target_course,
                    metadata_filters=metadata_filters,
                    strict_filter=strict_filter,
                )
                ensemble_retriever = EnsembleRetriever(
                    retrievers=[pinecone_retriever, es_retriever],
                    weights=[0.5, 0.5],
                )
                candidate_docs = await ensemble_retriever.ainvoke(query)
            else:
                logger.info("Elasticsearch not available. Using Pinecone only.")
                candidate_docs = await pinecone_retriever.ainvoke(query)

            if not candidate_docs:
                return []

            # --- BƯỚC 2: KHỬ TRÙNG LẶP ---
            unique_docs: dict[str, Document] = {}
            for doc in candidate_docs:
                if doc.page_content not in unique_docs:
                    unique_docs[doc.page_content] = doc

            deduplicated_docs = list(unique_docs.values())
            num_docs = len(deduplicated_docs)

            # --- BƯỚC 3: MỞ RỘNG TỪ ĐỒNG NGHĨA & RERANK BẰNG MAX-POOLING ---
            queries_list = self._expand_query_with_synonyms(query, max_expansion=4)
            doc_contents = [doc.page_content for doc in deduplicated_docs]

            all_pairs = [
                [q_var, content]
                for q_var in queries_list
                for content in doc_contents
            ]

            # CrossEncoder đã áp dụng nn.Sigmoid() -> trả về xác suất [0, 1]
            raw_scores = await asyncio.to_thread(self.rerank_model.predict, all_pairs)
            score_matrix = np.asarray(raw_scores, dtype=np.float64).reshape(
                len(queries_list), num_docs
            )
            max_scores = np.max(score_matrix, axis=0)

            # --- BƯỚC 4: SOFT COURSE BOOSTING (chỉ khi không strict_filter) ---
            BONUS_SCORE = 0.15
            adjusted_scores = []
            for doc, score in zip(deduplicated_docs, max_scores):
                final_score = float(score)
                doc_course = doc.metadata.get("course_name")
                if not strict_filter and target_course and doc_course == target_course:
                    final_score = min(1.0, final_score + BONUS_SCORE)
                adjusted_scores.append(final_score)

            scored_docs = sorted(
                zip(deduplicated_docs, adjusted_scores),
                key=lambda x: x[1],
                reverse=True,
            )

            # --- BƯỚC 5: LỌC THEO THRESHOLD VÀ TRẢ VỀ KẾT QUẢ ---
            final_docs = []
            for doc, score in scored_docs:
                if score < threshold:
                    break
                doc.metadata["rerank_score"] = round(score, 4)
                final_docs.append(doc)
                if len(final_docs) >= k_return:
                    break

            logger.info(
                "FINISH RERANKING (threshold=%.2f, total_retrieved=%d)",
                threshold,
                len(final_docs),
            )
            return final_docs

        except Exception as e:
            logger.exception("Có lỗi khi thực hiện search_with_rerank: %s", e)
            return []


class VectorDatabaseSingleton:
    _instance: VectorDatabase | None = None

    @staticmethod
    def get() -> VectorDatabase:
        if VectorDatabaseSingleton._instance is None:
            logger.info("Khởi tạo VectorDatabase lần đầu tiên...")
            VectorDatabaseSingleton._instance = VectorDatabase()

        return VectorDatabaseSingleton._instance
