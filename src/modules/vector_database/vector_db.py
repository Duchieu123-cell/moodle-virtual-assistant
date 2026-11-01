from src.modules.file_processor.service import FileProcessService
from src.modules.vector_database.synonyms import synonym_list
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.retrievers import EnsembleRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from elasticsearch import AsyncElasticsearch, helpers
from langchain_core.retrievers import BaseRetriever
from langchain_pinecone import PineconeVectorStore
from sentence_transformers import CrossEncoder
from pinecone import Pinecone, ServerlessSpec
from langchain_core.documents import Document
from fastapi import HTTPException, status
from src.core.config import settings
from typing import Optional
import numpy as np
import itertools
import asyncio
import uuid
import re

PINECONE_API_KEY = settings.PINECONE_API_KEY
ES_URL = settings.ES_URL
ES_INDEX_NAME = PINECONE_INDEX_NAME = "moodle-files"


# ===============================================================
# CLASS CUSTOM RETRIEVER CHO ELASTICSEARCH (BM25 + SOFT BOOSTING)
# ===============================================================
class ElasticsearchBM25Retriever(BaseRetriever):
    """
    Custom Retriever thực hiện tìm kiếm BM25 trực tiếp trên Elasticsearch,
    hỗ trợ ưu tiên (boost) theo course_name ngay từ tầng truy vấn.
    """
    client: AsyncElasticsearch
    index_name: str
    k: int
    target_course: Optional[str] = None

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> list[Document]:
        raise NotImplementedError("Use ainvoke instead for async support")

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> list[Document]:
        # Sử dụng bool query: Bắt buộc khớp nội dung text (must), và ưu tiên khớp course_name (should)
        should_clauses = []
        if self.target_course:
            should_clauses.append({
                "match_phrase": {
                    "metadata.course_name": {
                        "query": self.target_course,
                        "boost": 2.0  # Tăng điểm BM25 cho tài liệu thuộc đúng môn học
                    }
                }
            })

        search_query = {
            "size": self.k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "text": {
                                    "query": query,
                                    "fuzziness": "AUTO"
                                }
                            }
                        }
                    ],
                    "should": should_clauses
                }
            }
        }

        response = await self.client.search(index=self.index_name, body=search_query)

        documents = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            doc = Document(
                page_content=source.get("text", ""),
                metadata=source.get("metadata", {})
            )
            documents.append(doc)

        return documents


# ===============================================================
# MAIN VECTOR DATABASE CLASS
# ===============================================================
class VectorDatabase:
    def __init__(self):
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self._ensure_pinecone_index()

        # 1. Model Embedding Đa ngôn ngữ (Hỗ trợ tốt Tiếng Việt + Tiếng Anh, giữ nguyên 768 chiều)
        print("Loading Multilingual Embedding Model...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            encode_kwargs={"normalize_embeddings": True}
        )

        # 2. Khởi tạo Elasticsearch Client
        print(f"Đang kết nối đến Elasticsearch tại {ES_URL}...")
        try:
            self.es_client = AsyncElasticsearch(
                hosts=[ES_URL],
                verify_certs=False,
                request_timeout=60
            )
            print("Elasticsearch client đã được khởi tạo.")
        except Exception as e:
            print(f"Lỗi kết nối đến Elasticsearch: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi kết nối đến Elasticsearch: {e}"
            )

        # 3. Khởi tạo Reranker Đa ngôn ngữ (hỗ trợ Tiếng Việt & Tiếng Anh)
        print("Loading Multilingual Rerank Model...")
        self.rerank_model = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")

        # 4. Chuẩn bị Dictionary cho việc map từ đồng nghĩa
        self.synonym_dict = self._build_synonym_dict(synonym_list)

    def _build_synonym_dict(self, raw_synonyms: list[str]) -> dict:
        """
        Biến đổi danh sách synonym thành dictionary (hỗ trợ gộp nếu 1 từ xuất hiện ở nhiều dòng).
        """
        syn_dict = {}
        for line in raw_synonyms:
            terms = [t.strip().lower() for t in line.split(",") if t.strip()]
            for term in terms:
                others = [t for t in terms if t != term]
                if term not in syn_dict:
                    syn_dict[term] = []
                for o in others:
                    if o not in syn_dict[term]:
                        syn_dict[term].append(o)
        return syn_dict

    def _expand_query_with_synonyms(self, query: str, max_Expansion: int = 4) -> list[str]:
        """
        Mở rộng câu truy vấn với từ đồng nghĩa, giới hạn số lượng tổ hợp tối đa (max_Expansion)
        để tránh bùng nổ tổ hợp làm nghẽn CPU khi Rerank.
        """
        if not self.synonym_dict:
            return [query]

        sorted_keys = sorted(self.synonym_dict.keys(), key=len, reverse=True)
        # Dùng lookbehind/lookahead khoảng trắng hoặc đầu/cuối câu để bắt chuẩn tiếng Việt có dấu
        pattern_str = r'(?<!\w)(' + '|'.join(map(re.escape, sorted_keys)) + r')(?!\w)'
        pattern = re.compile(pattern_str, re.IGNORECASE)

        tokens = pattern.split(query)
        options_per_token = []

        for token in tokens:
            if not token:
                options_per_token.append([token])
                continue

            token_lower = token.lower()
            if token_lower in self.synonym_dict:
                synonyms = self.synonym_dict[token_lower]
                options = [token] + synonyms
                options_per_token.append(options)
            else:
                options_per_token.append([token])

        expanded_queries = [query]  # Luôn ưu tiên câu truy vấn gốc ở vị trí đầu tiên
        for combination in itertools.product(*options_per_token):
            full_sentence = "".join(combination)
            if full_sentence not in expanded_queries:
                expanded_queries.append(full_sentence)
            if len(expanded_queries) >= max_Expansion:
                break

        return expanded_queries

    def _ensure_pinecone_index(self):
        """
        Đảm bảo Index trên Pinecone đã tồn tại (768 dimensions).
        """
        try:
            existing_indexes = [i.name for i in self.pc.list_indexes()]
            if PINECONE_INDEX_NAME not in existing_indexes:
                self.pc.create_index(
                    PINECONE_INDEX_NAME,
                    dimension=768,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
                print(f"Pinecone index '{PINECONE_INDEX_NAME}' đã được tạo.")
        except Exception as e:
            print(f"Lỗi khi tạo index Pinecone: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi tạo index Pinecone: {e}"
            )

    def _get_pinecone_store(self) -> PineconeVectorStore:
        return PineconeVectorStore(
            embedding=self.embedding_model,
            index_name=PINECONE_INDEX_NAME,
            pinecone_api_key=PINECONE_API_KEY
        )

    async def _create_es_index_if_not_exists(self):
        """
        Kiểm tra và tạo Index trong Elasticsearch với cấu hình tiếng Việt.
        """
        if not await self.es_client.indices.exists(index=ES_INDEX_NAME):
            print(f"Creating index {ES_INDEX_NAME} with Vietnamese Plugin config...")
            await self.es_client.indices.create(
                index=ES_INDEX_NAME,
                body={
                    "settings": {
                        "analysis": {
                            "filter": {
                                "my_synonym_graph": {
                                    "type": "synonym_graph",
                                    "synonyms": synonym_list,
                                    "expand": True
                                }
                            },
                            "analyzer": {
                                "vi_search_analyzer": {
                                    "tokenizer": "vi_tokenizer",
                                    "filter": ["lowercase", "my_synonym_graph"]
                                },
                                "vi_index_analyzer": {
                                    "tokenizer": "vi_tokenizer",
                                    "filter": ["lowercase"]
                                }
                            }
                        }
                    },
                    "mappings": {
                        "properties": {
                            "text": {
                                "type": "text",
                                "analyzer": "vi_index_analyzer",
                                "search_analyzer": "vi_search_analyzer"
                            },
                            "metadata": {
                                "type": "object"
                            }
                        }
                    }
                }
            )

    async def add_file_to_index(self, file_path: str, metadata: dict) -> bool:
        """
        Trích xuất nội dung từ file, chia chunk bảo toàn cấu trúc Bảng/Vision,
        và lưu đồng bộ (Upsert) vào Pinecone + Elasticsearch.
        """
        try:
            print(f"-------------- Processing file: {file_path} --------------")
            # --- BƯỚC 1: TRÍCH XUẤT NỘI DUNG TỪ FILE PROCESS SERVICE ---
            docs = await FileProcessService.process_file(file_path, metadata)
            if not docs:
                print("No valid content extracted from file.")
                return False

            print(f"Extracted {len(docs)} valid pages from file.")

            # --- BƯỚC 2: CHIA CHUNK BẢO TOÀN BẢNG & MÔ TẢ HÌNH ẢNH ---
            # Ưu tiên giữ nguyên khối Bảng dữ liệu và khối Phân tích Hình ảnh/Sơ đồ
            text_splitter = RecursiveCharacterTextSplitter(
                separators=[
                    "\n\n[Nội dung phân tích từ Hình ảnh/Sơ đồ]\n",
                    "\n\n[Bảng dữ liệu",
                    "\n\n",
                    "\n",
                    ". ",
                    " ",
                    ""
                ],
                chunk_size=1200,
                chunk_overlap=200,
                length_function=len,
                add_start_index=True
            )
            splits = text_splitter.split_documents(docs)
            if not splits:
                return False

            # --- BƯỚC 3: BỔ SUNG NGỮ CẢNH ĐẦU CHUNK & TẠO DETERMINISTIC ID ---
            chunk_ids = []
            for idx, split in enumerate(splits):
                filename = split.metadata.get("filename", "")
                course_name = split.metadata.get("course_name", "")
                page_num = split.metadata.get("page", 1)
                start_idx = split.metadata.get("start_index", idx)

                # Gắn ngữ cảnh ngắn gọn vào đầu chunk nếu chunk chưa có tiêu đề rõ ràng
                header_ctx = f"[Tài liệu: {filename} | Trang {page_num}]"
                if course_name:
                    header_ctx = f"[Môn: {course_name} | Tài liệu: {filename} | Trang {page_num}]"
                
                if not split.page_content.startswith("[Môn:") and not split.page_content.startswith("[Tài liệu:"):
                    split.page_content = f"{header_ctx}\n{split.page_content}"

                # Tạo ID cố định (UUID5) theo file + trang + vị trí chunk để chống trùng lặp khi re-index
                unique_key = f"{course_name}_{filename}_p{page_num}_i{start_idx}_{idx}"
                deterministic_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_key))
                chunk_ids.append(deterministic_id)

            print(f"Split into {len(splits)} contextualized chunks for indexing.")

            # --- BƯỚC 4: UPSERT VÀO PINECONE ---
            print("Adding to Pinecone...")
            vector_store = self._get_pinecone_store()
            await vector_store.aadd_documents(documents=splits, ids=chunk_ids)
            print("Pinecone add done.")

            # --- BƯỚC 5: UPSERT VÀO ELASTICSEARCH ---
            if self.es_client:
                print("Adding to Elasticsearch...")
                if not await self.es_client.ping():
                    print("Cannot ping Elasticsearch!")
                    return False

                await self._create_es_index_if_not_exists()

                actions = []
                for split, doc_id in zip(splits, chunk_ids):
                    action = {
                        "_op_type": "index",  # Ghi đè nếu _id đã tồn tại
                        "_index": ES_INDEX_NAME,
                        "_id": doc_id,
                        "_source": {
                            "text": split.page_content,
                            "metadata": split.metadata
                        }
                    }
                    actions.append(action)

                success_count, failed = await helpers.async_bulk(
                    self.es_client, actions, raise_on_error=False
                )
                print(f"Elasticsearch add result: {success_count} docs indexed, {len(failed)} failed.")

            print("------------------------------------ Ending processing file ------------------------------------")
            return True

        except Exception as e:
            print(f"Lỗi khi xử lý file: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def search_with_rerank(
        self,
        query: str,
        k_return: int,
        k_search: int,
        threshold: float,
        metadata_filters: dict = None
    ) -> list[Document]:
        """
        Tìm kiếm Hybrid (Pinecone + Elasticsearch) kết hợp Max-Pooling Cross-Encoder Rerank.
        """
        try:
            print(f"-------------- START SEARCHING: '{query}' --------------")
            target_course = metadata_filters.get("course_name") if metadata_filters else None
            if target_course:
                print(f"Applying soft course boost for: {target_course}")

            # --- BƯỚC 1: RETRIEVAL (Thu thập ứng viên) ---
            vector_store = self._get_pinecone_store()
            pinecone_retriever = vector_store.as_retriever(search_kwargs={"k": k_search})

            if self.es_client and await self.es_client.ping():
                es_retriever = ElasticsearchBM25Retriever(
                    client=self.es_client,
                    index_name=ES_INDEX_NAME,
                    k=k_search,
                    target_course=target_course
                )
                print("Using Hybrid Search (Pinecone + Custom Elasticsearch BM25)")
                ensemble_retriever = EnsembleRetriever(
                    retrievers=[pinecone_retriever, es_retriever],
                    weights=[0.5, 0.5]
                )
                candidate_docs = await ensemble_retriever.ainvoke(query)
            else:
                print("Elasticsearch not available. Using Pinecone only.")
                candidate_docs = await pinecone_retriever.ainvoke(query)

            if not candidate_docs:
                return []

            # --- BƯỚC 2: KHỬ TRÙNG LẶP ---
            unique_docs = {}
            for doc in candidate_docs:
                if doc.page_content not in unique_docs:
                    unique_docs[doc.page_content] = doc

            deduplicated_docs = list(unique_docs.values())
            num_docs = len(deduplicated_docs)
            print(f"Reranking {num_docs} unique candidate documents...")

            # --- BƯỚC 3: MỞ RỘNG TỪ ĐỒNG NGHĨA & RERANK BẰNG MAX-POOLING ---
            queries_list = self._expand_query_with_synonyms(query, max_Expansion=4)
            print(f"Expanded into {len(queries_list)} query variants: {queries_list}")

            doc_contents = [doc.page_content for doc in deduplicated_docs]

            # Gom toàn bộ cặp (query_variant, doc_content) để chạy batch 1 lần duy nhất
            all_pairs = []
            for q_var in queries_list:
                for content in doc_contents:
                    all_pairs.append([q_var, content])

            # Chạy CrossEncoder trên thread riêng để không làm treo Event Loop của FastAPI
            raw_scores = await asyncio.to_thread(self.rerank_model.predict, all_pairs)
            raw_scores = np.array(raw_scores).reshape(len(queries_list), num_docs)

            # Max-Pooling: Điểm của mỗi Document là điểm cao nhất mà nó đạt được trước các biến thể câu hỏi
            max_raw_scores = np.max(raw_scores, axis=0)

            # --- BƯỚC 4: SIGMOID NORMALIZATION & SOFT BOOSTING ---
            sigmoid_scores = 1 / (1 + np.exp(-max_raw_scores))

            BONUS_SCORE = 0.15
            adjusted_scores = []
            for doc, score in zip(deduplicated_docs, sigmoid_scores):
                doc_course = doc.metadata.get("course_name")
                if target_course and doc_course == target_course:
                    score = min(1.0, float(score) + BONUS_SCORE)
                adjusted_scores.append(float(score))

            scored_docs = list(zip(deduplicated_docs, adjusted_scores))
            sorted_docs = sorted(scored_docs, key=lambda x: x[1], reverse=True)

            # --- BƯỚC 5: LỌC THEO THRESHOLD VÀ TRẢ VỀ KẾT QUẢ ---
            final_docs = []
            for i, (doc, score) in enumerate(sorted_docs):
                filename = doc.metadata.get("filename", "Unknown")
                page = doc.metadata.get("page", 0)
                start_index = doc.metadata.get("start_index", 0)

                if score < threshold:
                    print(f"{i+1}. File {filename}, page {page}, start_index {start_index}, score {score:.4f} | Skipped from here (< {threshold})")
                    break

                print(f"{i+1}. File {filename}, page {page}, start_index {start_index}, score {score:.4f} | Accepted")
                # Lưu kèm điểm rerank vào metadata để tiện debug hoặc hiển thị độ tin cậy
                doc.metadata["rerank_score"] = round(score, 4)
                final_docs.append(doc)

                if len(final_docs) >= k_return:
                    break

            print(f"-------------- FINISH RERANKING (threshold: {threshold}, total retrieved: {len(final_docs)}) --------------")
            return final_docs

        except Exception as e:
            print(f"Có lỗi khi thực hiện search_with_rerank: {e}")
            import traceback
            traceback.print_exc()
            return []


class VectorDatabaseSingleton:
    _instance: VectorDatabase | None = None

    @staticmethod
    def get() -> VectorDatabase:
        if VectorDatabaseSingleton._instance is None:
            print("Khởi tạo VectorDatabase lần đầu tiên...")
            VectorDatabaseSingleton._instance = VectorDatabase()

        return VectorDatabaseSingleton._instance