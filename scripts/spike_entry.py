"""Entrypoint mínimo do spike: força imports pesados e sobe /health."""
import pynfe
import lxml.etree
import cryptography
from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "libs": ["pynfe", "lxml", "cryptography"]}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
