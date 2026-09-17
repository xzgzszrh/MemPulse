"""Browser verification transport for the desktop UI; packaged apps use stdio instead.

Serves the same dispatcher the Electron bridge talks to, over loopback HTTP, so
the OpenCode web preview (`bun run --cwd packages/app dev`) and the Tauri UI dev
server can render real memory data without a native shell. Loopback only.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mempulse.desktop import DesktopService
import uvicorn

service = DesktopService(Path(os.environ.get('MEMPULSE_PREVIEW_DATA_DIR') or Path(__file__).resolve().parents[1] / '.mempulse' / 'desktop-preview'))

@asynccontextmanager
async def lifespan(app):
    yield
    service.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r'^https?://(localhost|127\.0\.0\.1)(:\d+)?$',
    allow_methods=['POST', 'OPTIONS'],
    allow_headers=['content-type'],
)

@app.post('/api/desktop')
def desktop(request: dict):
    try:
        return {'ok': True, 'data': service.dispatch(request['method'], request.get('params'))}
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=51984)
