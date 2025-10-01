from bottle import response, Request
from charset_normalizer.cli import query_yes_no
from fastapi import  FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import os
from dotenv import load_dotenv
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import logging
import uvicorn
#from validator import validate_priority # Função customizada

# --- Configuração Inicial ---
load_dotenv()

app = FastAPI(
    title="TaskMaster API",
    description="API completa para gerenciamento de tarefas com Supabase",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuração Supabase ---
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("Variáveis de ambiente SUPABASE_URL e SUPABASE_KEY não configuradas!")

supabase = create_client(supabase_url, supabase_key)


# --- Modelos Pydantic ---
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None # Campo opcional
    priority: int = 3


    @validator('priority')
    def validate_priority(cls, v):
        if v not in range(1, 6):
            raise ValueError('Priority deve ser entre 1 e 5')
        return v

class TaskCreate(TaskBase):
    user_id: str

class TaskResponse(TaskCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    is_completed: bool

# --- Rotas ---
@app.get("/")
async def root():
    return {
        "message": "Bem-vindo à TaskMaster API!",
        "docs": "Acesse /docs para a documentação Swagger"
    }

@app.post("/tasks/",
         response_model=TaskResponse,
         status_code=status.HTTP_201_CREATED,
         summary="Cria nova tarefa",
         tags=["Tasks"])
async def create_task(task: TaskCreate):
    """"
    Retorna lista peginada de tarefas com filtos opcionais.

    Parâmetros:
    - **title**: Título da tarefa (obrigatorio)
    - **description**: Descrição detalhada (opcional)
    - **user_id**: ID do usuário associado (obrigatorio)
    - **priority**: Nível de prioridade (1-5, padrão=3)
    """
    try:
        response = supabase.table("tasks").insert(task.dict()).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao criar tarefa"
            )
        return response.data[0]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/tasks/",
         response_model=List[TaskResponse],
         summary="Lista todas as tarefas",
         tags=["Tasks"])
async  def list_tasks(
    skip: int = 0,
    limit: int = 10,
    completed: Optional[bool] = None,
    user_id: Optional[str] = None
):
    """
    Retorna lista paginada de tarefas com filtros opcionais.

    Parâmetros:
    - **skip**: Quantidade de registros para pular (paginação)
    - **limit**: Limite de registros por página (default=10)
    - **completed**: Filtro por status (true/false)
    - **user_id**: Filtro por ID do usuário
    """
    try:
        query = supabase.table("tasks").select("*")

        if completed is not None:
            query = query.eq("is_completed", completed)
        if user_id:
            query = query.eq("user_id", user_id)

        response = query.range(skip, skip + limit - 1).execute()
        return response.data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# --- Rotas de Health Check ---
@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# --- Middleware de Log ---
logging.basicConfig(
    filename='api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@app.middleware("http")
async  def log_requests(request: Request, call_next):
    response = await call_next(request)
    logging.info(
        f"Method={request.method} "
        f"Path={request.url.path} "
        f"Status={response.status_code}"
    )
    return response

# --- Execução ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )