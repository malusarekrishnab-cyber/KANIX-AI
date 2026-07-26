import os
import threading
import traceback
from typing import Optional, List, Dict
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# Singleton for embedding model
_model = None
_model_lock = threading.Lock()

# Embedding cache
_embedding_cache = {}
_cache_lock = threading.Lock()
_cache_max_size = 200

# Supabase connection
_client: Optional[Client] = None
_client_lock = threading.Lock()

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                print("[Memory DB] Loading BGE-M3 embedding model...")
                try:
                    _model = SentenceTransformer("BAAI/bge-m3")
                    print("[Memory DB] BGE-M3 Model loaded")
                except Exception as e:
                    print(f"[Memory DB] Failed to load BGE-M3: {e}")
                    raise
    return _model

def get_supabase_client() -> Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                url = os.environ.get("SUPABASE_URL")
                key = os.environ.get("SUPABASE_SECRET_KEY")
                if not url or not key:
                    raise ValueError("Supabase credentials not found")
                
                print("[Memory DB] Connecting to Supabase...")
                _client = create_client(url, key)
    return _client

def get_embedding(text: str) -> List[float]:
    if not text.strip():
        return []
    
    text = text.strip()
    
    with _cache_lock:
        if text in _embedding_cache:
            return _embedding_cache[text]
    
    model = get_embedding_model()
    embedding = model.encode(text).tolist()
    
    with _cache_lock:
        if len(_embedding_cache) >= _cache_max_size:
            _embedding_cache.pop(next(iter(_embedding_cache)))
        _embedding_cache[text] = embedding
    
    return embedding

def save_memory(text: str) -> Optional[Dict]:
    """Save text to memory with embedding (only content and embedding)"""
    if not text or not text.strip() or len(text.strip()) < 10:
        return None
    
    text = text.strip()
    
    try:
        client = get_supabase_client()
        
        # Duplicate detection
        existing = client.table("kanix_memory").select("id").eq("content", text).execute()
        if existing.data:
            print("[Memory DB] Duplicate memory found, skipping insert")
            return existing.data[0]
        
        embedding = get_embedding(text)
        if not embedding:
            return None
            
        data = {
            "content": text,
            "embedding": embedding
        }
        
        result = client.table("kanix_memory").insert(data).execute()
        if result.data:
            print(f"[Memory DB] Saved: '{text[:50]}...'")
            return result.data[0]
            
    except Exception as e:
        print(f"[Memory DB] Save error: {e}")
        
    return None

def query_memory(query: str, match_threshold: float = 0.5, match_count: int = 5) -> str:
    """Query memory for similar content using RPC"""
    if not query or not query.strip():
        return ""
        
    try:
        client = get_supabase_client()
        query_embedding = get_embedding(query)
        if not query_embedding:
            return ""
            
        response = client.rpc("match_kanix_memory", {
            "query_embedding": query_embedding,
            "match_threshold": match_threshold,
            "match_count": match_count
        }).execute()
        
        results = response.data
        if not results:
            return ""
            
        context_parts = []
        for i, r in enumerate(results, 1):
            content = r.get("content", "")
            if content:
                context_parts.append(f"{i}. {content}")
                
        return "\n".join(context_parts)
        
    except Exception as e:
        print(f"[Memory DB] Query error: {e}")
        return ""