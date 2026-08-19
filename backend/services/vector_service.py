from qdrant_client import models
from core.qdrant import client
import uuid
from fastapi import HTTPException
async def exist_collection(pdf_id: str) -> bool:
    try:
        await client.get_collection(pdf_id)
        return True
    except Exception as e:
        print(f"Qdrant error: {type(e).__name__}: {e}")
        return False

async def create_collection(pdf_id: str):
    await client.create_collection(
        collection_name=pdf_id,
        vectors_config={
            "content_dense_vector": models.VectorParams(size=768, 
            distance=models.Distance.DOT,
            hnsw_config=models.HnswConfigDiff(
                m=32,
                ef_construct=64,
                full_scan_threshold=100
            ),
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, always_ram=True, quantile=0.99)
            ),
            on_disk=True
            )
        },
        sparse_vectors_config={
            "heading_sparse_vector": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False),modifier=models.Modifier.IDF)
        },
    )

async def store_vectors(pdf_id: str, chunks: list[dict], vectors: list[list[float]], avg_doc_length: float):
    if not await exist_collection(pdf_id):
        await create_collection(pdf_id)
    points = build_points(chunks, vectors, avg_doc_length)
    client.upload_points(collection_name=pdf_id,
                         batch_size=64,
                         parallel=4,
                    points=points)


def build_points(chunks_payload: list[dict], vectors: list[list[float]], avg_doc_length: float) -> list[models.PointStruct]:
    points=[
        models.PointStruct(
            id=uuid.uuid4().hex,
            vector={
                "content_dense_vector": vector,
                "heading_sparse_vector": models.Document(
                    text=payload["heading"] or "",
                    options={"language": "english", "avg_len": avg_doc_length},
                    model="Qdrant/bm25",
                ),
            },
            payload={"heading": payload["heading"], "content": payload["content"], "page_no": payload["page_no"], "filename": payload["filename"]},
        )
        for payload,vector in zip(chunks_payload, vectors)
        ]
    return points

async def delete_collection(pdf_id: str):
    if await exist_collection(pdf_id):
        await client.delete_collection(pdf_id)
        print(f"Collection {pdf_id} deleted successfully.")
    else:
        print(f"Collection {pdf_id} does not exist. No deletion performed.")

async def retrieve_results(pdf_id: str, prefetch: list[models.Prefetch]):
    if not await exist_collection(pdf_id):
        raise HTTPException(status_code=403, detail=f"Session {pdf_id} not found.Please reupload the document and try again.")
    
    results = await client.query_points(
        collection_name=pdf_id,
        prefetch=prefetch,
        query=models.RrfQuery(rrf=models.Rrf(weights=[1.5, 1.0])),
        search_params=models.SearchParams(
            quantization=models.QuantizationSearchParams(rescore=False)
        ),
        with_payload=True,
        limit=5,
    )
    return results