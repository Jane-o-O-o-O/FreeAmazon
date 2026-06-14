# Amazon-Agent

Amazon-Agent is an MVP scaffold for finding similar 1688 wholesale sources from an Amazon product link.

The current version runs a complete pipeline in mock mode by default:

```text
Amazon URL
  -> Canopy API product data or local mock data
  -> Apify 1688 candidates or local mock data
  -> mock CLIP similarity ranking
  -> React result page
```

The Canopy REST adapter and Apify/SiliconFlow 1688 source-search adapters are implemented. Apify and CLIP still default to mock adapters so the MVP can run without paid credentials.

## Stack

- API: FastAPI
- Web: Vite + React + TypeScript
- Future database: PostgreSQL + pgvector
- Future queue/cache: Redis
- Future ranking: local CLIP model

## Local Development

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

To use real Amazon product data from Canopy, set:

```env
CANOPY_API_KEY=your_canopy_api_key
CANOPY_API_BASE_URL=https://rest.canopyapi.co
CANOPY_USE_MOCK=false
```

To use real 1688 source data from Apify, set:

```env
APIFY_API_TOKEN=your_apify_api_token
APIFY_API_BASE_URL=https://api.apify.com/v2
APIFY_USE_MOCK=false
APIFY_REVERSE_IMAGE_ACTOR=dev00/alibaba-1688-aliexpress-reverse-image-search-api
APIFY_KEYWORD_SEARCH_ACTOR=ecomscrape/1688-product-search-scraper
APIFY_REVERSE_IMAGE_DESTINATION=1688
```

SiliconFlow can optionally improve Chinese keyword generation:

```env
SILICONFLOW_API_KEY=your_siliconflow_key
SILICONFLOW_USE_MOCK=false
```

Run the API:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the web app in another terminal:

```powershell
cd apps/web
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

API health check:

```text
http://localhost:8000/health
```

## Docker Development

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## API Contract

Create a source search task:

```http
POST /api/source-search/tasks
```

Example body:

```json
{
  "amazon_url": "https://www.amazon.com/dp/B0C1234567",
  "marketplace": "US",
  "filters": {
    "max_price_cny": null,
    "factory_only": false,
    "dropshipping": false,
    "min_supplier_years": null
  }
}
```

Get task:

```http
GET /api/source-search/tasks/{task_id}
```

Get results:

```http
GET /api/source-search/tasks/{task_id}/results
```

## Next Development Steps

1. Validate Apify Actor output shapes against more Amazon categories and extend field normalizers.
2. Replace `ClipService.image_similarity` with local CLIP embeddings.
3. Add PostgreSQL persistence for tasks, products, images, and ranked source items.
4. Move the synchronous pipeline into a background worker.
