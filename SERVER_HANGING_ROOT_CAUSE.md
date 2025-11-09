# Server Hanging Root Cause Analysis

## Problem Summary
Server pages (HTML templates) hang after a few successful requests. API endpoints work initially but eventually timeout.

## Investigation Timeline

### 1. Initial Diagnosis
- **Symptom**: Homepage and dashboard pages timeout after 3-5 seconds
- **Observation**: HTTP middleware logging was causing hangs

### 2. First Fix Attempt
- **Action**: Disabled HTTP logging middleware completely
- **Result**: Partial success - some requests work, then hangs resume

### 3. Scheduler/Telegram Investigation  
- **Action**: Disabled ENABLE_SCHEDULER and TELEGRAM_BOT_ENABLED
- **Result**: No change - still hanging

### 4. Connection Analysis
- **Finding**: CLOSE_WAIT and FIN_WAIT2 connections with unsent data (78-87 bytes)
- **Interpretation**: Server generating responses but not sending them

### 5. Pattern Identification
**What Works:**
- Simple JSON endpoints: `/health`, `/test`
- API endpoints (initially): `/api/signals`, `/api/system/status`

**What Fails:**
- Portfolio API: `/api/portfolio/summary` (makes external IIFL calls with 8s timeout)
- ALL HTML template pages: `/`, `/signals`, `/portfolio`, `/backtest`, `/settings`

## Root Cause

### **Jinja2 Template Rendering is Blocking the Async Event Loop**

**Evidence:**
1. All template-based routes timeout consistently
2. JSON endpoints work fine
3. Portfolio API (with external HTTP calls) also times out
4. Pattern: Anything that does I/O blocks subsequent requests

**Technical Explanation:**
- Jinja2Templates().TemplateResponse() is **synchronous**
- FastAPI runs on async uvicorn with a single event loop
- When template rendering blocks, it prevents other requests from being processed
- Connection pool fills up, subsequent requests timeout

### Why It Works Initially
- First few requests complete before blocking becomes severe
- Once several templates are being rendered, the event loop is blocked
- New connections queue up and timeout

## Solutions

### Option 1: Use run_in_executor for Template Rendering (RECOMMENDED)
```python
from concurrent.futures import ThreadPoolExecutor
import functools

executor = ThreadPoolExecutor(max_workers=10)

@app.get("/")
async def dashboard(request: Request):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        executor,
        functools.partial(templates.TemplateResponse, "dashboard.html", {"request": request})
    )
    return response
```

### Option 2: Use Starlette's BackgroundTasks
Not suitable for templates as we need the response immediately.

### Option 3: Serve Static Pre-rendered HTML
Generate static HTML files and serve with StaticFiles middleware.

### Option 4: Use a Frontend Framework
React/Vue/Svelte with API backend (microservices architecture).

### Option 5: Increase Uvicorn Workers
Not viable with lifespan context manager (scheduler, DB connections).

## Immediate Fix

**Disable template routes temporarily and use API + separate frontend:**

```python
# Comment out all template routes
# @app.get("/")
# async def dashboard(request: Request):
#     return templates.TemplateResponse("dashboard.html", {"request": request})

# Serve a simple JSON response instead
@app.get("/")
async def dashboard_redirect():
    return {"message": "Use /api/* endpoints or access dashboard via separate frontend"}
```

## Long-term Solution

**Implement Option 1** - Wrap all `templates.TemplateResponse()` calls in `loop.run_in_executor()` to run template rendering in a thread pool, preventing event loop blocking.

## Status
- **Current**: Server hanging due to blocking template rendering
- **Workaround**: Use API endpoints directly, avoid HTML pages
- **Fix**: Requires code changes to make template rendering async-safe
