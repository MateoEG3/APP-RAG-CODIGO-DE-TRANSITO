import re
import fitz  # pymupdf
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

# ── Configuración ──────────────────────────────────────────
PDF_PATH = "data/codigo_transito.pdf"
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "codigo_transito"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Prioriza cortar en el inicio de un artículo antes que en párrafo/línea/espacio
SEPARATORS = ["\nArtículo ", "\n\n", "\n", " ", ""]


# ── 1. Leer y limpiar PDF ───────────────────────────────────
def extract_pages(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            text = re.sub(r"-\s*\n\s*", "", text)   # une palabras cortadas por guion
            text = re.sub(r"\n+", "\n", text)        # colapsa saltos de línea repetidos
            pages.append({"page": i + 1, "text": text})
    print(f"✅ PDF leído: {len(pages)} páginas con contenido")
    return pages


# ── 2. Dividir en chunks respetando límites de artículo ────
def make_chunks(pages):
    splitter = RecursiveCharacterTextSplitter(
        separators=SEPARATORS,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = []
    for p in pages:
        for piece in splitter.split_text(p["text"]):
            if len(piece.strip()) > 50:
                chunks.append({"text": piece.strip(), "page": p["page"]})
    print(f"✅ Chunks creados: {len(chunks)}")
    return chunks


# ── 3. Generar embeddings y guardar en ChromaDB ────────────
def store_in_chroma(chunks, chroma_path=CHROMA_PATH):
    print("⏳ Cargando modelo de embeddings...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=chroma_path)

    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
        print("🔄 Colección anterior eliminada")

    collection = client.create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    texts = [c["text"] for c in chunks]
    print("⏳ Generando embeddings (puede tomar un momento)...")
    embeddings = model.encode(texts, show_progress_bar=True)

    collection.add(
        ids=[f"chunk_{i}" for i in range(len(chunks))],
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=[{"page": c["page"]} for c in chunks],
    )
    print(f"✅ {len(chunks)} chunks almacenados en ChromaDB")


# ── Main ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Iniciando ingesta del documento...\n")
    pages = extract_pages(PDF_PATH)
    chunks = make_chunks(pages)
    store_in_chroma(chunks)
    print("\n✅ Ingesta completada. Base de datos vectorial lista.")