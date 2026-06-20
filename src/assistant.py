import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

# ── Configuración ──────────────────────────────────────────
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "codigo_transito"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
GROQ_MODEL = "llama-3.3-70b-versatile"
TOP_K = 5
SIMILARITY_THRESHOLD = 0.95  # distancia máxima aceptable (menor = más similar)

ASSISTANT_NAME = "VíaLex"
ASSISTANT_ROLE = "asistente especializado en el Código Nacional de Tránsito de Colombia (Ley 769 de 2002)"

SYSTEM_PROMPT = f"""Eres {ASSISTANT_NAME}, {ASSISTANT_ROLE}.

Reglas estrictas:
1. Responde ÚNICAMENTE con información del contexto proporcionado.
2. Si la respuesta NO está en el contexto, di explícitamente: "Esta información no se encuentra en el Código Nacional de Tránsito consultado."
3. Sé claro, preciso y usa lenguaje accesible para cualquier ciudadano colombiano.
4. No inventes artículos, cifras ni sanciones que no estén en el contexto.
5. No incluyas al final la sección de páginas consultadas, eso se agrega automáticamente."""

# ── Cargar recursos ────────────────────────────────────────
def load_resources():
    print(f"⏳ Cargando {ASSISTANT_NAME}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    print(f"✅ {ASSISTANT_NAME} listo.\n")
    return model, collection, groq_client

# ── Recuperar chunks relevantes con umbral ─────────────────
def retrieve(query, model, collection, top_k=TOP_K):
    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
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

# ── Generar respuesta con Groq ──────────────────────────────
def generate_answer(query, chunks, groq_client):
    if not chunks:
        return "Esta información no se encuentra en el Código Nacional de Tránsito consultado."

    context = "\n\n".join(
        [f"[Página {c['page']}]\n{c['text']}" for c in chunks]
    )
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
        return f"⚠️ No se pudo generar la respuesta (error de la API: {type(e).__name__}: {e}). Intenta de nuevo en unos segundos."

    # Solo agregamos páginas si el LLM realmente encontró la respuesta en el contexto
    no_encontrado = "no se encuentra en el código nacional de tránsito" in answer.lower()
    if not no_encontrado:
        answer += f"\n\n📄 Páginas consultadas: {', '.join(map(str, pages))}"

    return answer

# ── Bucle conversacional ───────────────────────────────────
def main():
    model, collection, groq_client = load_resources()

    print("=" * 60)
    print(f"  {ASSISTANT_NAME} — Código Nacional de Tránsito")
    print("  Escribe 'salir' para terminar")
    print("=" * 60)

    while True:
        print()
        query = input("🧑 Tú: ").strip()

        if not query:
            continue
        if query.lower() in ["salir", "exit", "quit"]:
            print(f"\n{ASSISTANT_NAME}: ¡Hasta luego! Conduce con precaución. 🚗")
            break

        chunks = retrieve(query, model, collection)
        answer = generate_answer(query, chunks, groq_client)

        print(f"\n🤖 {ASSISTANT_NAME}: {answer}")

if __name__ == "__main__":
    main()