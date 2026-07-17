from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="QBitLeap")


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>QBitLeap</title>
    </head>
    <body style="background:#111;color:white;font-family:Arial;padding:40px;">
        <h1>QBitLeap</h1>
        <h2>Qbit Solo Miner</h2>

        <p>Backend is running.</p>

        <hr>

        <p>Qbit Core:
        <strong>Not Connected</strong></p>

        <p>CKPool:
        <strong>Not Running</strong></p>
    </body>
    </html>
    """
