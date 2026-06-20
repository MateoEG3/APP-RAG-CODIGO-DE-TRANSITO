import os
import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "codigo_transito"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
GROQ_MODEL = "llama-3.3-70b-versatile"
TOP_K = 5
SIMILARITY_THRESHOLD = 0.95

ASSISTANT_NAME = "VíaLex"

SYSTEM_PROMPT = """Eres VíaLex, asistente especializado en el Código Nacional de Tránsito de Colombia (Ley 769 de 2002).

Reglas estrictas:
1. Responde ÚNICAMENTE con información del contexto proporcionado.
2. Si la respuesta NO está en el contexto, di explícitamente: "Esta información no se encuentra en el Código Nacional de Tránsito consultado."
3. Sé claro, preciso y usa lenguaje accesible para cualquier ciudadano colombiano.
4. No inventes artículos, cifras ni sanciones que no estén en el contexto.
5. No incluyas al final la sección de páginas consultadas, eso se agrega automáticamente."""

_resources = None

def get_resources():
    global _resources
    if _resources is None:
        print("⏳ Cargando recursos RAG...")
        model = SentenceTransformer(EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(COLLECTION_NAME)
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        _resources = (model, collection, groq_client)
        print("✅ Recursos cargados.")
    return _resources

def retrieve(query):
    model, collection, _ = get_resources()
    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"]
    )
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        if dist <= SIMILARITY_THRESHOLD:
            chunks.append({"text": doc, "page": meta["page"], "distance": dist})
    return chunks

def generate_answer(query):
    _, _, groq_client = get_resources()
    chunks = retrieve(query)

    if not chunks:
        return {
            "answer": "Esta información no se encuentra en el Código Nacional de Tránsito consultado.",
            "pages": []
        }

    context = "\n\n".join([f"[Página {c['page']}]\n{c['text']}" for c in chunks])
    pages = sorted(set(c["page"] for c in chunks))

    user_prompt = f"""--- CONTEXTO RECUPERADO ---
{context}
--- FIN DEL CONTEXTO ---

Pregunta del usuario: {query}

Responde basándote únicamente en el contexto anterior."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return {
            "answer": f"⚠️ Error al generar respuesta: {type(e).__name__}. Intenta de nuevo.",
            "pages": []
        }

    return {"answer": answer, "pages": pages}