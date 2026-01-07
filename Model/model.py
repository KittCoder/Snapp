
from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI

key = "your_openai_api_key_here"  # Replace with your actual OpenAI API key

client = OpenAI(api_key=key)

app = Flask(__name__, static_folder="../Web", static_url_path="")

SYSTEM_PROMPT = (
    "You are a helpful meal generating assistant who generates concise meal ideas only. "
    "Names, not recipes."
)


def generate_reply(message):
    response = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        store=True,
    )
    return response.output_text, response.usage.total_tokens


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "main.html")


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400
    try:
        reply, total_tokens = generate_reply(message)
    except Exception:
        return jsonify({"error": "Model request failed."}), 500
    return jsonify({"reply": reply, "usage": {"total_tokens": total_tokens}})


if __name__ == "__main__":
    app.run(debug=True)
