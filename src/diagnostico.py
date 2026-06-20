import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_collection("codigo_transito")

# Traer todos los chunks y buscar manualmente los que mencionan embriaguez
all_data = collection.get(include=["documents", "metadatas"])
for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
    if "embriaguez" in doc.lower():
        print(f"Página {meta['page']}: {doc[:150]}")
        print("---")