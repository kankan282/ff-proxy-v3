from flask import Flask, request, jsonify
import time
import random
import string
import uuid
import os
import base64
from datetime import datetime

app = Flask(__name__)

# ══════════════════════════════
# GUEST SYSTEM  
# ══════════════════════════════

class GuestSystem:
    def __init__(self):
        self.guests = {}
        self.resets_today = 0

    def generate_identity(self):
        prefixes = ['hwid_samsung_','hwid_xiaomi_','hwid_realme_',
                     'hwid_oneplus_','hwid_poco_','hwid_vivo_']
        return {
            'guest_id': f"guest_{uuid.uuid4().hex[:16]}",
            'hwid': f"{random.choice(prefixes)}{''.join(random.choices(string.hexdigits[:16],k=8))}",
            'android_id': base64.b64encode(os.urandom(8)).decode().replace('=','').replace('/','0'),
            'advertising_id': str(uuid.uuid4()),
            'mac_address': f"{random.choice(['A4:83:E7','34:DF:3A','CC:B2:55'])}:{':'.join(f'{random.randint(0,255):02X}' for _ in range(3))}",
            'device_brand': random.choice(['Samsung','Xiaomi','realme','OnePlus','POCO']),
            'device_model': random.choice(['SM-A145F','M2010J19SG','RMX3085']),
            'android_ver': random.choice(['11','12','13']),
        }

    def register(self):
        ident = self.generate_identity()
        self.guests[ident['guest_id']] = ident
        return ident

    def reset(self, old_gid):
        if old_gid in self.guests:
            del self.guests[old_gid]
        new = self.register()
        self.resets_today += 1
        return {'old': old_gid, 'new': new}

guest_sys = GuestSystem()

# ══════════════════════════════
# CONFIG PAYLOAD BUILDER
# ══════════════════════════════

def build_config():
    """This is what the game ACTUALLY expects to receive"""
    return {
        "code": 200,
        "msg": "OK",
        "data": {
            "version": "2.95.1",
            "configUrl": "https://ff-proxy-v3-4.onrender.com/",
            
            # Format A: features object
            "features": {
                "aimbot": {"on": True, "fov": 90, "smooth": 3, "silent": True},
                "fakeHeadshot": {"on": True, "visualOnly": True, "rate": 65},
                "noRecoil": True,
                "noSpread": True,
                
                "esp": {
                    "on": True,
                    "box": True,
                    "healthBar": True,
                    "nameTag": True,
                    "distanceText": True,
                    "lineOfSight": True,
                    "itemEsp": True,
                    "antennaHead": True
                },
                
                "player": {"speedMult": 1.07, "noFallDmg": True},
                
                "safety": {
                    "ssCleaner": True,
                    "statsCloak": {"kdMax": 8.5, "hsRatioMax": 42},
                    "shadowAutoOn": True
                }
            },
            
            # Format B: flat toggle list (some mods use this)
            "toggles": {
                "esp_on": 1,
                "aim_on": 1,
                "norecoil_on": 1,
                "fake_hs_on": 1,
                "speed_on": 1,
                "ss_clean_on": 1
            },
            
            # Format C: mod menu data
            "menu": {
                "name": "[ O N Y X ]",
                "version": "4.2"
            },
            
            # Format D: raw flags array (oldest format)
            "flags": [1, 1, 1, 1, 1, 1, 0],
            
            "guestResetEndpoint": "/api/guest_reset",
            "guestRegEndpoint": "/api/guest_register",
        },
        
        # Some APKs read root-level fields directly
        "config_version": 42,
        "server_time": int(time.time()),
        "status": "ok",
        "maintenance": False,
        "_signature": "ONYX_ACTIVE"
    }

# ══════════════════════════════
# CATCH-ALL ROUTE (THE FIX!)
# ══════════════════════════════

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'HEAD', 'OPTIONS'])
def catch_all(path):
    """
    ANY URL that hits this server gets config back.
    No more 404. Game can hit anything.
    """
    print(f"[REQUEST] {request.method} {path} from {request.remote_addr}")
    
    # Return config regardless of what was requested
    resp = build_config()
    
    # Log which path the game actually wants (so we know)
    resp['_debug_request_path'] = path if path else '/'
    resp['_debug_method'] = request.method
    
    return jsonify(resp)

# ══════════════════════════════
# SPECIFIC API ROUTES (bonus)
# ══════════════════════════════

@app.route('/api/guest_register', methods=['POST'])
def guest_register():
    ident = guest_sys.register()
    return jsonify({"code": 200, "msg": "OK", "data": ident})

@app.route('/api/guest_reset', methods=['POST'])
def guest_reset():
    data = request.get_json() or {}
    old_gid = data.get('guestId') or data.get('guest_id') or ''
    result = guest_sys.reset(old_gid)
    ni = result['new']
    return jsonify({
        "code": 200, "msg": "RESET_OK",
        "data": ni,
        "_note": "Update localconfig.json HWID then restart"
    })

@app.route('/ping')
def ping():
    return jsonify({"status": "awake", "ts": time.time()})

@app.route('/health')
def health():
    return jsonify({"ok": True, "svc": "onyx_v4", "g": len(guest_sys.guests)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 45)
    print("  ONYX v4 — CATCH-ALL MODE")
    print("  All URLs return config. No more 404.")
    print(f"  Port: {port}")
    print("=" * 45)
    app.run(host='0.0.0.0', port=port)
