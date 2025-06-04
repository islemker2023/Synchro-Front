import logging
import os
from Package import AI_file_path
from sentence_transformers import SentenceTransformer
import json, requests, numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, request, jsonify, Blueprint, url_for

bp = Blueprint('rag', __name__)
routes_logger = logging.getLogger('routes')


with open(AI_file_path, "r", encoding="utf-8") as f:
    knowledge = json.load(f)

model = SentenceTransformer("all-MiniLM-L6-v2")
docs = [f"{item['title']}: {item['content']}" for item in knowledge]
doc_embedding = model.encode(docs)

def retrieve_context(query, k=2):
    query_embedding = model.encode([query])
    similarity = cosine_similarity(query_embedding, doc_embedding)[0]
    top_indices = np.argsort(similarity)[-k:][::-1]
    top_docs = [docs[i] for i in top_indices]
    return "\n".join(top_docs)

GEMENI_API_KEY = "AIzaSyBD41l5Xlsz8bm1GAW780uqIukxki7tMcI"

chat_history = []
@bp.route("/chat", methods=["POST"])
def chat():
    data = request.json
    query = data.get("message", "")
    if not query:
        return jsonify({"error": "Missing message"}), 400

    # 1. Add the user's message to history
    chat_history.append({
        "role": "user",
        "parts": [{"text": query}]
    })

    # 2. Get context and build the prompt
    context = retrieve_context(query)
    full_prompt = f"{context}\n\nUser question: {query} and dont write options"

    # 3. Add prompt to history and call Gemini
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMENI_API_KEY}"
    payload = {
        "contents": chat_history + [{"role": "user", "parts": [{"text": full_prompt}]}]
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(API_URL, headers=headers, json=payload)

    if not response.ok:
        return jsonify({"error": response.json().get("error", {})}), 500

    reply = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    # 4. Add the model's response to history
    chat_history.append({
        "role": "model",
        "parts": [{"text": reply}]
    })

    return jsonify({"response": reply})