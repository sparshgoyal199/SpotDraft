import modal
#EmbeddingModel = modal.Cls.from_name("embeddings-generator", "EmbeddingModel")
parsing_and_embedding_model = modal.Cls.from_name("parsing_and_embedding_generator", "ParsingEmbeddingModel")

async def generate_embeddings(query: str = None, chunks: list[dict] = None):
    #embedObj = EmbeddingModel()
    modal_obj = parsing_and_embedding_model()
    if query:
        return await modal_obj.embed_query.remote.aio(query)
    else:
        return await modal_obj.embed_chunks.remote.aio(chunks)
    