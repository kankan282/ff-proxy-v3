from flask import Flask, jsonify, make_response
import os
import time
import threading

app = Flask(__name__)

# Keep-alive ping every 14 min so Render never sleeps
def keep_alive():
    import urllib.request
    while True:
        try:
            urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','5000')+'/ping')
        except: pass
        time.sleep(840)

t = threading.Thread(target=keep_alive, daemon=True)
t.start()

# ─── THE ONE CONFIG THE GAME NEEDS ───

GAME_CFG = {
    "ret": 0,
    "msg": "ok",
    "code": 200,
    "version": "2.95.1",
    "versionCode": 29512047,
    "status": "success",
    
    # All features ON as flat int (1 = on)
    "esp": 1,
    "aimbot": 1,
    "norecoil": 1,
    "nospread": 1,
    "fakehs": 1,
    "speed": 107,
    "antenna": 1,
    "itemesp": 1,
    "ssclean": 1,
    "antiban": 1,
    
    "menu_name": "[ O N Y X ]",
    "menu_version": "5.0",
    
    # Guest reset
    "resetEnabled": 1,
    "resetUrl": "/api/guest_reset",
    "regUrl": "/api/guest_register",
    
    # Timestamp (game checks freshness)
    "ts": 0  
}

@app.route('/ping')
def ping():
    return jsonify({"alive": 1})

@app.route('/', defaults={'p': ''})
@app.route('/<path:p>', methods=['GET','POST','HEAD','OPTIONS'])
def catch(p):
    # Update timestamp each request
    GAME_CFG["ts"] = int(time.time() * 1000)
    
    resp = make_response(jsonify(GAME_CFG))
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Cache-Control'] = 'no-cache'
    resp.status_code = 200
    return resp

if __name__ == '__main__':
    app.run('0.0.0.0', int(os.environ.get('PORT',5000)))
