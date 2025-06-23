import os

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from datetime import datetime
from typing import List

app = FastAPI()


DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000",
        "sslmode": "disable"
    },
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    username = Column(String)
    task_name = Column(String)
    deadline = Column(String)



class TaskCreate(BaseModel):
    user_id: int
    username: str
    task_name: str
    deadline: str


class TaskResponse(BaseModel):
    id: int
    user_id: int
    username: str
    task_name: str
    deadline: str


@app.on_event("startup")
async def startup_event():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
        raise



@app.get("/tasks/{user_id}", response_model=List[TaskResponse])
async def get_user_tasks(user_id: int):
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.user_id == user_id).all()
        return tasks
    finally:
        db.close()


@app.post("/tasks", response_model=TaskResponse)
async def create_task(task: TaskCreate):
    # Проверка формата даты
    try:
        datetime.strptime(task.deadline, "%d.%m.%Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте ДД.ММ.ГГГГ")

    db = SessionLocal()
    try:
        db_task = Task(
            user_id=task.user_id,
            username=task.username,
            task_name=task.task_name,
            deadline=task.deadline
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании задачи: {str(e)}")
    finally:
        db.close()


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Задача не найдена")

        db.delete(task)
        db.commit()
        return {"message": f"Задача {task_id} успешно удалена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении задачи: {str(e)}")
    finally:
        db.close()