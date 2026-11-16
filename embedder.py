"""One shared multilingual embedding model; vectors normalized for cosine search."""
from functools import lru_cache
import numpy as np

MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

@lru_cache(maxsize=1)
def get_model():
    import os
    import torch
    torch.set_num_threads(int(os.getenv("EMBEDDING_THREADS", "2")))
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME, device='cpu')

def embed(texts):
    return np.asarray(get_model().encode(texts, normalize_embeddings=True,
                                        show_progress_bar=False), dtype='float32')
