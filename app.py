import os
from flask import Flask, render_template, request, jsonify
from src.rag import generate_answer, ASSISTANT_NAME

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html", assistant_name=ASSISTANT_NAME)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    query = (data.get("message", "") if data else "").strip()
    if not query:
        return jsonify({"answer": "Por favor escribe una pregunta.", "pages": []})
    result = generate_answer(query)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=False, port=5000)