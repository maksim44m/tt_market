from fastapi import FastAPI

from bot_api.broadcast.services import (BroadcastRequest,
                                        broadcast_message)

app = FastAPI()


@app.post(path="/api/broadcast/")
async def broadcast(request: BroadcastRequest):
    msg, errors = await broadcast_message(request.message)
    return {"status": "ok", 'message': msg, 'errors': errors}
