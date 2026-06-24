from app import app, init_db

init_db()
app.testing = True
client = app.test_client()

endpoints = ['/', '/journey', '/explore', '/api/spots/goa', '/spot/1', '/dashboard']

for ep in endpoints:
    try:
        resp = client.get(ep)
        print(f"GET {ep} -> {resp.status_code} (len={len(resp.get_data(as_text=True))})")
    except Exception as e:
        print(f"GET {ep} -> EXCEPTION: {e}")

# Test API chatbot
try:
    resp = client.post('/api/chatbot', json={'message': 'hi'})
    print(f"POST /api/chatbot -> {resp.status_code} {resp.get_data(as_text=True)[:200]}")
except Exception as e:
    print(f"POST /api/chatbot -> EXCEPTION: {e}")

# Test search API
try:
    resp = client.get('/api/search?q=goa')
    print(f"GET /api/search?q=goa -> {resp.status_code} {resp.get_data(as_text=True)[:200]}")
except Exception as e:
    print(f"GET /api/search?q=goa -> EXCEPTION: {e}")
