from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db import DB
from app.routers import analytics, auth, tasks, topics

app = FastAPI(
    title="Трекер задач",
    description="Итоговое задание по спецглавам баз данных. Колегов Сергей.",
    version="1.0.0",
)
app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(tasks.router)
app.include_router(analytics.router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {key: error[key] for key in ("type", "loc", "msg")}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.get("/", include_in_schema=False)
def docs() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", tags=["Service"])
def readiness(db: DB) -> dict[str, str]:
    try:
        db.scalar(select(1))
    except OperationalError as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"status": "ok"}
