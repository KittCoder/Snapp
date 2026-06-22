# SNAPP
A web application that generates healthy recipes for SNAP benefits users, using AI on the backend. Checks local grocery store availability.

## Run locally
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your_api_key_here"
   ```
3. Start the app:
   ```bash
   python Model/model.py
   ```
4. Open `http://localhost:5000` in your browser.

The frontend sends chatbot requests to `/chat`, and the backend forwards them to the OpenAI API. The Information tab calls `/grocery-stores?zip=12345` and uses OpenStreetMap's Nominatim and Overpass services to return grocery stores without an additional API key.
