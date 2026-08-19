from qdrant_client import models
from services.vector_service import retrieve_results
from fastapi.responses import StreamingResponse
from core.llm import groq_client, llm
import json

def prompt_formatter(query: str, 
                     formatted_chunks: str) -> str:

    user_prompt = f"""
        Context:
        {formatted_chunks}

        Question:
        {query}
        """
    return user_prompt

def format_retrieved_chunks(relevant_chunks_payload: list[dict]) -> str:
    formatted_chunks = ""
    for idx,chunk in enumerate(relevant_chunks_payload):
        formatted_chunks += f"[chunk {idx}]\n"
        formatted_chunks += f"heading: {chunk['heading']}\n"
        formatted_chunks += f"content: {chunk['content']}\n"
        formatted_chunks += f"page_no: {chunk['page_no']}\n"
        formatted_chunks += f"filename: {chunk['filename']}\n\n"
    return formatted_chunks


async def retrieve__llm_response(messages: list) -> StreamingResponse:
    response = await llm.ainvoke(messages)
    return response

async def retrieve_relevant_chunks(pdf_id: str, embedded_query: list[float], original_query: str):
    result_payload = []
    prefetch = [
        models.Prefetch(
            query=embedded_query,
            using="content_dense_vector",
            limit=20,
        ),
        models.Prefetch(
            query=models.Document(text=original_query, model="Qdrant/bm25"),
            using="heading_sparse_vector",
            limit=20,
        ),
    ]

    results = await retrieve_results(pdf_id, prefetch)
    for resp in results.points:
        result_payload.append({
            "heading": resp.payload.get("heading", ""),
            "content": resp.payload.get("content", ""),
            "page_no": resp.payload.get("page_no", ""),
            "filename": resp.payload.get("filename", "")
        })
    return result_payload

def creating_user_prompt(relevant_chunks_payload, query):
    formatted_chunks = format_retrieved_chunks(relevant_chunks_payload)
    prompt = prompt_formatter(query, formatted_chunks)
    return prompt

async def response_generator(messages: list):
    llm_response = await retrieve__llm_response(messages)
    return llm_response
