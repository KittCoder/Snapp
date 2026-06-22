# SNAPP

SNAPP is a web application that generates healthy meal ideas for SNAP benefits users and finds nearby grocery stores. The frontend deploys to Vercel, the Flask API deploys to Render, and Supabase is reserved for persistent data when the application needs it.

## Project structure

```text
.
├── Web/                 # Static frontend deployed by Vercel
│   ├── index.html
│   ├── app.js
│   └── looks.css
├── Model/               # Flask API deployed by Render
│   ├── model.py
│   └── requirements.txt
├── render.yaml          # Render Blueprint
└── vercel.json          # Vercel build configuration
```

## Run locally

Start the backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r Model/requirements.txt
export OPENAI_API_KEY="your_api_key_here"
python Model/model.py
```

In another terminal, serve the frontend:

```bash
python3 -m http.server 5173 --directory Web
```

Then open `http://localhost:5173`. During local development the frontend automatically calls the Flask API at `http://localhost:5000`.

## Deploy the backend to Render

1. In Render, create a Blueprint from this repository. Render reads `render.yaml` and creates the `snapp-api` free web service.
2. Provide `OPENAI_API_KEY` when prompted.
3. Initially set `CORS_ORIGINS` to your Vercel URL, such as `https://snapp.vercel.app`. Multiple origins can be comma-separated.
4. After deployment, copy the Render URL, such as `https://snapp-api.onrender.com`.

The API exposes `GET /health`, `POST /chat`, and `GET /grocery-stores?zip=12345`.

## Deploy the frontend to Vercel

1. Import this repository into Vercel. The root `vercel.json` disables install and build commands and publishes `Web/` directly.
2. Deploy the project with Framework Preset set to `Other`.
3. If a Render backend is available, set the `snapp-api-base-url` meta tag in `Web/index.html` to its HTTPS URL and redeploy.
4. Add the final Vercel URL to `CORS_ORIGINS` in Render and redeploy the backend.

The backend URL is public frontend configuration. OpenAI and Supabase service-role keys must remain backend-only.

## Supabase preparation

No database client is installed yet because the application does not currently persist data. When persistence is added:

- Keep `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in Render environment variables.
- Never expose the service-role key to the browser.
- Use Supabase Row Level Security for any browser-accessible tables.
- Replace the in-memory global chat history before scaling; it is process-local and is currently shared across requests.

The expected variable names are documented in `Model/.env.example`.

## Free-tier behavior

Render free web services spin down after inactivity, so the first API request after an idle period can be noticeably slower. The filesystem is ephemeral; persistent application data should go to Supabase rather than local files.
