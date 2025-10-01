from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import os
from dotenv import load_dotenv
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import logging
import uvicorn

# --- Configuração inicial ---
load_dotenv()

app = FastAPI(
    title="TaskMaster API",
    description="API for managing tasks",
    version="1.0",
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Supabase ---
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("Supabase URL and Supabase API key must be set")

try:
    supabase = create_client(supabase_url, supabase_key)
    print("✅ Conexão Supabase estabelecida!")
except Exception as e:
    print(f"❌ Erro na conexão Supabase: {e}")
    supabase = None


# --- Models ---
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 3

    @validator('priority')
    def validate_priority(cls, v):
        if v not in range(1, 6):
            raise ValueError("Priority must be between 1 and 5")
        return v


class TaskCreate(TaskBase):
    user_id: str


class TaskResponse(TaskCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    is_completed: bool


# --- Debug Route ---
@app.get("/debug-supabase")
async def debug_supabase():
    try:
        # Teste simples
        test_response = supabase.table("tasks").select("id").limit(1).execute()
        return {
            "status": "success",
            "supabase_connected": True,
            "test_response": str(test_response),
            "data": test_response.data if hasattr(test_response, 'data') else "No data"
        }
    except Exception as e:
        return {
            "status": "error",
            "supabase_connected": False,
            "error": str(e),
            "python_version": "3.13"
        }


# --- Routes ---
@app.get("/")
async def root():
    return {"message": "Task Master API running!", "docs": "/docs"}


@app.post("/tasks/", response_model=TaskResponse)
async def create_task(task: TaskCreate):
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available")

    try:
        # Converter para dict e garantir que está serializável
        task_data = task.dict()
        print(f"📝 Tentando criar tarefa: {task_data}")

        response = supabase.table("tasks").insert(task_data).execute()

        print(f"📨 Resposta bruta: {response}")

        if hasattr(response, 'data') and response.data:
            return response.data[0]
        else:
            raise HTTPException(status_code=400, detail="No data returned from database")

    except Exception as e:
        print(f"💥 Erro detalhado: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/tasks/", response_model=List[TaskResponse])
async def list_tasks(skip: int = 0, limit: int = 10, user_id: Optional[str] = None):
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection not available")

    try:
        query = supabase.table("tasks").select("*")

        if user_id:
            query = query.eq("user_id", user_id)

        response = query.range(skip, skip + limit - 1).execute()

        if hasattr(response, 'data'):
            return response.data
        else:
            return []

    except Exception as e:
        print(f"💥 Erro ao buscar tarefas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# --- Health Check ---
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "supabase_connected": supabase is not None
    }


# --- Configuração de Log ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logging.info(f"{request.method} {request.url.path} - {response.status_code}")
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)