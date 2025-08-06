from fastapi import  FastAPI, HTTPException, Depends, status
from supabase import create_client
import os
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional # Adicionado para campos opcionais

# Carrega variáveis de ambiente
load_dotenv()
# Configuração do Supabase

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Variáveis de ambeinte SUPABASE_KEY não configuradas! "
        "Crie um arquivo .env com SUPABASE_URL E SUPABASE_KEY"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Configuração inicial (mantenha isso no topo). (Crie a instância do FastAPI)
app = FastAPI(
    title="TaskMaster API",
    description="API para gerenciamento de tarefas com Supabase",
    version="1.0.0",
    openapi_tags=[{
        "name": "tasks",
        "description": "Operações com tarefas"
    }]
)

# 3. Modelos Pydantic (adicione novos modelos aqui)
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None # Campo opcional
    user_id: str

class TaskResponse(TaskCreate):
    id: str
    created_at: str
    is_completed: bool = False

# 4. Rotas existentes (mantenha as que ja funcionam)
@app.get("/", summary="Status da API")
async def health_check():
    return {"status": "online", "service": "TaskMaster API"}

@app.post("/tasks/",
          response_model=TaskResponse,
          status_code=status.HTTP_201_CREATED,
          tags=["tasks"],
          summary="Criar nova tarefa")
async def create_task(task: TaskCreate):
    try:
        # Insere no Supabase
        response = supabase.table("tasks").insert(task.dict()).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao criar tarefa")

        created_task = response.data[0]
        return TaskResponse(**created_task)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e))


# 5. Novas rotas (adicione abaixo das existentes)
@app.get("/tasks/{user_id}",
         response_model=list[TaskResponse],
         tags=["Tasks"],
         summary="Lista tarefa do usuário")
async def get_tasks(user_id: str):
    try:
        response = supabase.table("tasks")\
                        .select("*")\
                        .eq("user_id", user_id)\
                        .order("created_at", desc=True)\
                        .execute()
        return [TaskResponse(**task) for task in response.data]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao busca tarefa: {str(e)}"
        )

# Health Check
@app.get("/health", tag=["Health"])
async def health_check():
    try:
        # Testa conexão com Supabase
        supabase.table("tasks").select("*").limit(1).execute()
        return  {"status": "health"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Service unavailable")

# Mantenha isso no final do arquivo
if __name__ == "__main__":
    import unicorn
    unicorn.run(app, host="0.0.0.0", port=8000)