def ok(data):
    return {"code": 0, "message": "ok", "data": data}


def err(code, message):
    return {"code": code, "message": message, "data": None}
