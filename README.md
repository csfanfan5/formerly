# Google Forms Auto-Filler Backend (Vercel)

This folder contains a minimal serverless backend that proxies requests
from the Chrome extension to OpenAI.  The backend exposes a single
endpoint that accepts all questions from the current Google Form page
and responds with generated answers.

## Structure

```
vercel_backend/
├── api/
│   ├── answer_generator.py   # OpenAI + fallback logic
│   └── page_answers.py       # Flask endpoint for Vercel
├── requirements.txt          # Python dependencies
└── README.md
```

## Deploying to Vercel

1. Create a new Vercel project pointing at this directory.
2. Set the following environment variables (Project Settings → Environment Variables):

   - `OPENAI_API_KEY`: your OpenAI API key
   - `FORM_FILLER_MODEL` *(optional)*: override the default model
   - `ALLOWED_ORIGINS` *(optional)*: comma-separated list of origins
     that are allowed to call the endpoint (default `*`). Use the
     extension origin and any testing origins for production deployments.

3. Deploy:

   ```bash
   vercel
   vercel --prod  # when ready for production
   ```

4. After deployment, note the live URL of the API, e.g.
   `https://your-app.vercel.app/api/page_answers`. Use this value as the
   backend URL in the Chrome extension.

## Request/Response Schema

**Request** (`POST /api/page_answers`):

```json
{
  "facts": { "email": "student@example.com", "class_year": "2028" },
  "questions": [
    {
      "index": 0,
      "qtext": "Your name",
      "type": "text",
      "options": [],
      "required": true,
      "question_notes": []
    }
  ],
  "page_notes": ["Analyst End-of-Year Survey"]
}
```

**Response**:

```json
{
  "answers": {
    "0": "Cosine Cake"
  }
}
```

Checkbox answers return an array of option labels.

## Local Testing

Install dependencies and run the Flask app locally:

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...  # or set via direnv
vercel dev
```

or

```bash
pip install -r requirements.txt
export FLASK_APP=api/page_answers.py
flask run
```

Then send a request:

```bash
curl --request POST \
  --url http://127.0.0.1:5000/ \
  --header 'Content-Type: application/json' \
  --data '{"questions": [...], "page_notes": []}'
```

The local server accepts all origins (`*`) by default.
