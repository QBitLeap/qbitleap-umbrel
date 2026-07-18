from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from qbit import rpc

app = FastAPI(title="QBitLeap")


@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        blockchain = rpc("getblockchaininfo")
        qbit_status = (
            f"Connected — block {blockchain['blocks']}, "
            f"sync {blockchain['verificationprogress'] * 100:.2f}%"
        )
    except Exception as error:
        qbit_status = f"Not Connected — {type(error).__name__}"

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>QBitLeap</title>
    </head>
    <body style="background:#111;color:white;font-family:Arial;padding:40px;">
        <h1>QBitLeap</h1>
        <h2>Qbit Solo Miner</h2>

        <p>Backend is running.</p>

        <hr>

        <p>Qbit Core: <strong>{qbit_status}</strong></p>
        <p>CKPool: <strong>Not Running</strong></p>
    </body>
    </html>
    """
