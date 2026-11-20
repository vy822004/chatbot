# Lyftr AI Full-Stack Assignment: LLM Chatbot Gateway

A resilient, production-ready Full-Stack LLM Chatbot application featuring multi-turn conversation persistence with SQLite, LiteLLM automatic key pool failover, fast response caching, and per-request token usage tracking.

---

## 1. Live URLs
* **Frontend:** *[Deploy to Vercel/Netlify/Render and insert link here]*
* **Backend:** *[Deploy to Render/Railway/Fly.io and insert link here]*
* **Demo Video:** *[Insert 2–3 minute Loom or Google Drive link here]*

---

## 2. Run locally: with Docker and without

### Option A: With Docker (Recommended)
Make sure Docker and Docker Compose are installed and running.

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd Assignment
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Add your real Gemini / OpenAI API keys in .env
   ```

3. **Start services:**
   ```bash
   make up
   ```
   * Frontend: [http://localhost:3000](http://localhost:3000)
   * Backend: [http://localhost:8000](http://localhost:8000)
   * Backend Health: [http://localhost:8000/health](http://localhost:8000/health)

4. **Stop services:**
   ```bash
   make down
   ```

---

### Option B: Without Docker

#### Backend:
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure `.env`:
   ```bash
   cp ../.env.example .env
   ```
5. Run tests:
   ```bash
   pytest
   ```
6. Start the server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

#### Frontend:
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Vite dev server:
   ```bash
   npm run dev
   ```
   * Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 3. Design decisions: key fallback, caching, SQLite session storage

* **Key Pool & Auto-Fallback:**
  - Configured through `LLM_API_KEYS` as an ordered sequence of keys (`key_1`, `key_2`, ...).
  - LiteLLM gateway executes requests against active keys sequentially. When an HTTP 429, quota exhaustion, or 5xx provider error occurs, it catches the exception and immediately rotates to the next key in the pool, incrementing `fallback_attempts`.
  - If all keys are exhausted, a clean `503 {"detail": "all providers unavailable"}` is returned.
  - Failed requests are never saved to session history.

* **Response Caching:**
  - Employs LiteLLM's local built-in caching (`Cache(type="local")`).
  - Cache key is generated using `model + system_prompt + conversation_history + new_message`.
  - On a cache hit:
    - `"resolution_source": "LLM_CACHE"`
    - `key_id: null`
    - `fallback_attempts: 0`
    - Stored prompt/completion tokens are returned.
    - Measured latency is substantially lower than a live inference call.

* **SQLite Session Storage:**
  - Persisted in `/data/app.db` via a named Docker volume (`sqlite_data`) so that conversation history survives container restarts and redeployments.
  - Table `messages` tracks `id`, `session_id`, `role`, `content`, `metadata` (JSON), and `created_at` (ISO-8601).
  - Indexed on `session_id` for $O(1)$ indexed retrieval.

---

## 4. Verification: how to see failover, cache hits and per-message token usage

### 1. Verification of Cache Hits:
1. Open the UI at [http://localhost:3000](http://localhost:3000).
2. Send: `"What is the capital of France?"`
   * Metadata badge displays `LIVE_INFERENCE`, `key_id: key_1`, and normal latency (e.g. 500–800 ms).
3. Click **"+ New Session"** (or refresh the page) to start a brand new session.
4. Send the identical message: `"What is the capital of France?"`
   * Metadata badge immediately displays `LLM_CACHE`, `key_id: null`, and faster latency (< 50 ms).

### 2. Verification of Failover (`X-Simulate-Failure`):
The UI includes a **Failover Test Hook** selector in the sidebar:
* **Select `key_1=429`** and send a prompt:
  * Backend simulates 429 on `key_1` and seamlessly falls back to `key_2`.
  * Response badge displays `key_id: key_2` and `retries: 1` with HTTP 200.
* **Select `*=429`** and send a prompt:
  * Backend triggers failure on all keys and returns clean HTTP 503 (`"all providers unavailable"`).
  * UI displays the error gracefully inside the chat bubble without crashing.
  * Verified: no failed record is inserted into SQLite.

### 3. Verification of Per-Message Token Usage:
* Next to each AI message, separate `in:` and `out:` token badges show the exact token count for that prompt and completion, proving it is per-request rather than a cumulative running total.

---

## 5. Setup Used: your editor and AI tools
* **Editor:** VS Code / Cursor
* **AI Tooling:** Antigravity (Google DeepMind)
* **Testing:** Pytest, FastAPI TestClient, curl

---

## 6. Bonus features (if any): what you added beyond the requirements and why
1. **Interactive Failover Control in UI:** Built a direct dropdown selector in the sidebar for the `X-Simulate-Failure` header so reviewers can test key failover on demand in the demo video without needing terminal curl commands.
2. **Real-time Backend Health Monitor:** Header badge polls `/health` to show live connectivity, active key count, and cache status with visual indicators.
3. **Glassmorphic Modern UI & Markdown Support:** Rendered with Tailwind CSS v4 and `react-markdown` with syntax highlighting for code blocks, tables, and lists.
