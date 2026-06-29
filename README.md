# SNAPP
 
A web application that generates healthy recipes for SNAP benefits users, using AI on the backend. Checks local grocery store availability.
  
## Backend Deployment on Render 
                       
The backend is configured for Render with [render.yaml](/Users/2027kstarkie/Desktop/SNAPP/render.yaml:1).
 
1. Create a new Render Blueprint from this GitHub repository, or create a Web Service manually.
2. If using the blueprint, Render reads `render.yaml` automatically.
3. If creating the service manually, use these settings:
   - Root directory: `Model`
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn model:app`
   - Health check path: `/health`
4. Set these environment variables in Render:
   - `OPENAI_API_KEY`: your OpenAI API key
   - `FDC_API_KEY`: your USDA FoodData Central API key
   - `CORS_ORIGINS`: `https://snapp-1d5j.vercel.app`
 
Render injects `PORT` automatically. Gunicorn handles the hosted service process.

The backend also accepts Vercel deployment URLs that match this project, such as:

```text
https://snapp-1d5j-b7g466kuj-snapp-app.vercel.app
```

## Frontend on Vercel

After Render deploys the backend, copy the Render service URL and set it in [Web/index.html](/Users/2027kstarkie/Desktop/SNAPP/Web/index.html:7):

```html
<meta name="snapp-api-base-url" content="https://your-render-service.onrender.com" />
```

Then redeploy the static frontend to Vercel. The current allowed production frontend origin is:

```text
https://snapp-1d5j.vercel.app
```

## Supabase Auth

The frontend currently uses a temporary username/password flow backed by Supabase Auth. Usernames are converted into internal `@snapp.local` email addresses before calling Supabase. Personalized settings are stored in `public.user_info` with the row `id` matching the logged-in Auth user id. The app saves `zip_code`, `household_size`, `budget`, `dietary_preference`, `dietary_restrictions`, and `notifications_enabled`; `created_at` and `updated_at` are managed by the database.

Pantry items are stored in `public.user_pantry_items` and sent to the dish generator so meal ideas can account for food the user already has.

Selected stores are stored per user in `public.user_stores`.

In the Supabase dashboard, enable Email auth and disable email confirmation while this username prototype is active. Password reset emails will not work until the app moves to real email addresses.

## Local Backend

```sh
cd Model
pip install -r requirements.txt
OPENAI_API_KEY=your_key_here FDC_API_KEY=your_fdc_key_here python model.py
```

The API runs on `http://localhost:5000` locally.
 
