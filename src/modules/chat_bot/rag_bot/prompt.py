from langchain_core.prompts import PromptTemplate

PROMPT_REFINE = PromptTemplate.from_template("""
You are an expert search query optimizer for an educational chatbot.
Your goal is to extract the **core technical concepts** from the user's input for a search engine.

Rules:
    1. Remove conversational filler (e.g., "cho mình hỏi", "là gì", "như thế nào", "vui lòng cho biết", "what is").
    2. Remove general words that don't add meaning (e.g., "thông tin về", "chi tiết").
    3. Keep specific technical terms, acronyms (AI, IoT, ML), and proper nouns exactly as they are.
    4. Correct minor spelling mistakes if obvious.
    5. Do NOT add new words that are not in the original text.
    6. OUTPUT ONLY THE REFINED QUERY STRING. NO EXPLANATIONS.

Examples:
- Input: "Mô hình supervised learning trong machine learning là gì vậy?"
  -> Output: mô hình supervised learning machine learning
- Input: "Cho tôi xin tài liệu về giải thuật di truyền với"
  -> Output: giải thuật di truyền
- Input: "Edge computing hoạt động như thế nào?"
  -> Output: edge computing hoạt động

User's input:
"{input}"
""")

PROMPT_TRANSLATE = PromptTemplate.from_template("""
You are a translation assistant.

Task:
- If the input question is in Vietnamese, translate it into English.
- If the input question is in English, translate it into Vietnamese.

Rules:
- Only return the translated question.
- Do not explain, do not add extra text, do not include quotes.
- Keep the meaning accurate and natural.

Input:
{question}

Output:
""")

PROMPT_CHOOSE_DOCS = PromptTemplate.from_template("""
You are an assistant that used for choosing relevant documents based on user's input and given documents with high precision.                                                   
## Instructions:
    1. Given user's input and documents. A document includes ID, Source and its content.
    2. Determine the most appropriate documents based on the user's input by their IDs.
    3. An appropriate document is that whose content is exactly relevant to user's input content.
    4. Must: Strictly choose documents based on relevance to the user's input. Do not choose documents that are not relevant, even if they contain some related information.
    5. You must respond strictly in JSON format.

## Documents:
{documents}

## User's input:
"{input}"
    
## Suggested format for your JSON response:
{{
    "list_ids": [
        {{"id": 0}},
        {{"id": 2}},
        ...
    ]
}}
""")

PROMPT_RAG = PromptTemplate.from_template("""
You are an assistant within a learning system, help to provide guidance and assistance to users regarding learning content.

## Chat History:
{chat_history}

## Instructions:
    1. Based on User's input and Context to craft accurate responses.
    2. If uncertain, politely inform the user that you don't have the answer.
    3. When confident, provide concise and insightful assistance.
    4. Only use given documents in Context to answer.
    5. There may be some documents that are not relevant or overlapping, so try to synthesize the information and avoid redundancy in your suggestions. Focus on providing a clear and concise summary of the key points that are most relevant to the quiz questions.
    6. Respond to the user in their language, prioritizing Vietnamese whenever possible.
    7. Your response will be displayed in a chat interface, so make sure its format is HTML-friendly for better readability. (but not include img tags, only text formatting tags like <p>, <ul>, <li>, <strong>, <table>,  etc.)
    8. Hãy tham khảo Chat History để câu trả lời của bạn có tính kết nối, tự nhiên và liền mạch với những gì đã trao đổi trước đó.

## Context:
{context}

## User's input:
"{input}"
    
## Suggested format for your response:
<p>...</p>
""")