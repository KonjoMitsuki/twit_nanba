import uvicorn

uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=False)
