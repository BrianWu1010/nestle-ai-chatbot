from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# Serve the chat UI
@app.get("/")
def index_get():
    return render_template("base.html")

# Handle messages from the frontend
@app.post("/predict")
def predict():
    text = request.get_json().get("message")

    if not text:
        return jsonify({"answer": "Sorry, I didn't get that."})

    try:
        # Step 1: Retrieve slices from backend search
        response = requests.post("http://127.0.0.1:8000/search", json={"query": text})
        data = response.json()

        if "results" not in data or len(data["results"]) == 0:
            return jsonify({"answer": "Sorry, no relevant information found."})

        # Step 2: Get top 3 content chunks
        top_contents = [item["content"] for item in data["results"][:3]]

        # Step 3: Prepare prompt
        context_text = "\n\n".join(top_contents)
        system_prompt = "You are a helpful assistant answering questions based on product content from Nestlé Canada."
        user_prompt = f"Based on the following content, answer the user's question:\n\n{context_text}\n\nUser's question: {text}"

        # Step 4: Call OpenAI API
        import openai
        import os
        openai.api_key = os.getenv("OPENAI_API_KEY")  # replace with your actual key or use environment variable

        chat_completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or "gpt-4"
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        answer = chat_completion["choices"][0]["message"]["content"]
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"answer": f"Error during processing: {str(e)}"})

# Run the Flask app in debug mode
if __name__ == "__main__":
    app.run(debug=True)