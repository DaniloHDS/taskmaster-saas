from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import logging
import uvicorn
import sqlite3
import json
from contextlib import contextmanager

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

# --- SQLite Database ---
DATABASE_URL = "tasks.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row  # Para retornar dicionários
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute('''
                     CREATE TABLE IF NOT EXISTS tasks
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY
                         AUTOINCREMENT,
                         title
                         TEXT
                         NOT
                         NULL,
                         description
                         TEXT,
                         priority
                         INTEGER
                         DEFAULT
                         3,
                         user_id
                         TEXT
                         NOT
                         NULL,
                         is_completed
                         BOOLEAN
                         DEFAULT
                         FALSE,
                         created_at
                         TIMESTAMP
                         DEFAULT
                         CURRENT_TIMESTAMP,
                         updated_at
                         TIMESTAMP
                         DEFAULT
                         CURRENT_TIMESTAMP
                     )
                     ''')
        conn.commit()
        print("✅ Banco de dados SQLite inicializado!")


# Inicializar banco ao iniciar a API
init_db()


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
    id: int
    created_at: datetime
    updated_at: datetime
    is_completed: bool


# --- Routes ---
@app.get("/")
async def root():
    return {
        "message": "TaskMaster API running with SQLite!",
        "docs": "/docs",
        "database": "SQLite"
    }


@app.post("/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                           INSERT INTO tasks (title, description, priority, user_id)
                           VALUES (?, ?, ?, ?)
                           ''', (task.title, task.description, task.priority, task.user_id))

            conn.commit()
            task_id = cursor.lastrowid

            # Buscar tarefa criada
            cursor.execute('''
                           SELECT *,
                                  datetime(created_at) as created_at,
                                  datetime(updated_at) as updated_at
                           FROM tasks
                           WHERE id = ?
                           ''', (task_id,))

            task_data = cursor.fetchone()

            if not task_data:
                raise HTTPException(status_code=400, detail="Error creating task")

            # Converter para dicionário
            task_dict = dict(task_data)
            return task_dict

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/tasks/", response_model=List[TaskResponse])
async def list_tasks(
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[str] = None,
        completed: Optional[bool] = None
):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            query = '''
                    SELECT *,
                           datetime(created_at) as created_at,
                           datetime(updated_at) as updated_at
                    FROM tasks \
                    '''
            params = []

            conditions = []
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            if completed is not None:
                conditions.append("is_completed = ?")
                params.append(completed)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, skip])

            cursor.execute(query, params)
            tasks = cursor.fetchall()

            return [dict(task) for task in tasks]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT *,
                                  datetime(created_at) as created_at,
                                  datetime(updated_at) as updated_at
                           FROM tasks
                           WHERE id = ?
                           ''', (task_id,))

            task = cursor.fetchone()

            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            return dict(task)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task: TaskBase):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                           UPDATE tasks
                           SET title       = ?,
                               description = ?,
                               priority    = ?,
                               updated_at  = CURRENT_TIMESTAMP
                           WHERE id = ?
                           ''', (task.title, task.description, task.priority, task_id))

            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Task not found")

            # Buscar tarefa atualizada
            cursor.execute('''
                           SELECT *,
                                  datetime(created_at) as created_at,
                                  datetime(updated_at) as updated_at
                           FROM tasks
                           WHERE id = ?
                           ''', (task_id,))

            task_data = cursor.fetchone()
            return dict(task_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.put("/tasks/{task_id}/complete")
async def complete_task(task_id: int):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                           UPDATE tasks
                           SET is_completed = TRUE,
                               updated_at   = CURRENT_TIMESTAMP
                           WHERE id = ?
                           ''', (task_id,))

            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Task not found")

            return {"message": "Task completed successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Task not found")

            return {"message": "Task deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# --- Health Check ---
@app.get("/health")
async def health_check():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM tasks")
            count = cursor.fetchone()["count"]

            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "database": "SQLite",
                "total_tasks": count
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# --- Debug Routes ---
@app.get("/debug/database")
async def debug_database():
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Informações do banco
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as count FROM tasks")
            task_count = cursor.fetchone()["count"]

            return {
                "database": DATABASE_URL,
                "tables": [table["name"] for table in tables],
                "total_tasks": task_count,
                "python_version": "3.13"
            }
    except Exception as e:
        return {"error": str(e)}


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