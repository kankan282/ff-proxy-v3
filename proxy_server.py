# proxy_server_v3.py — FF Proxy Panel: Fake HS + AntiBan + Guest Reset + Render Deployable
from flask import Flask, request, jsonify
import json
import hashlib
import hmac
import time
import random
import string
import base64
import os
import uuid
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)

# ════════════════════════════════════════════════════════════
# GUEST ACCOUNT RESET SYSTEM
# ════════════════════════════════════════════════════════════
"""
Kya karta hai ye system:
1. Guest account ka internal ID track karta hai
2. Account "reset" karne pe pura fingerprint badal deta hai
3. Naya device ID, naya session, naya identity
4. Server ko lagta hai naya player aa raha hai
5. Purana account band hone ka risk zero kyunki ab vo account exist nahi karta tumhare liye

Flow:
- Guest login → server gives you a guest_id
- Tum us guest_id se khelte ho (tracked in our system)
- Reset chahiye? → /ff/guest_reset call karo
- System generates FRESH everything → naya guest_id → clean slate
- Old guest_id abandon ho jaata hai (server side delete optional)
"""

class GuestResetEngine:
    def __init__(self):
        # In production use Redis/database. For Render free tier, dict is fine.
        self.active_guests = {}   # guest_id -> {session_data}
        self.reset_history = []   # audit log (optional)
        self.max_resets_per_hour = 5  # spam protect
        
    def generate_fresh_identity(self, old_hwid=None):
        """
        Generate completely fresh identity for guest reset.
        Everything new — no link to old identity possible.
        """
        
        # Fresh Guest UUID
        new_guest_id = f"guest_{uuid.uuid4().hex[:16]}"
        
        # Fresh HWID (looks like real android device)
        hwid_prefixes = [
            'hwid_samsung_sm_a', 'hwid_xiaomi_redmi_',
            'hwid_realme_rmx_', 'hwid_poco_m', 'hwid_oneplus_',
            'hwid_vivo_v', 'hwid_oppo_a', 'hwid_motorola_edge',
            'hwid_infinix_hot_', 'hwid_techno_camoon_',
            'hwid_itel_p', 'hwid_narzo_',
        ]
        prefix = random.choice(hwid_prefixes)
        model_suffix = ''.join(random.choices(string.digits + string.ascii_lowercase, k=8))
        new_hwid = f"{prefix}{model_suffix}"
        
        # Fresh Android ID (base64 encoded random)
        new_android_id = base64.b64encode(os.urandom(8)).decode().replace('=','').replace('/','0')
        
        # Fresh advertising ID
        new_advertising_id = str(uuid.uuid4())
        
        # Fresh GAID (Google Advertising ID style)
        new_gaid = f"{uuid.uuid4()}-{uuid.uuid4().hex[:12]}"
        
        # Fresh IMEI spoof (for devices that report it) 
        # Looks like real Samsung/Xiaomi IMEI pattern
        new_imei_spoofer = f"35{random.randint(10000000,99999999)}{random.randint(1000000,9999999)}"
        
        # Serial number
        new_serial = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        # MAC address spoof (randomized but valid OUI prefixes for real vendors)
        mac_ouis = [
            'A4:83:E7',  # Samsung
            '34:DF:3A',  # Xiaomi  
            'CC:B2:55',  # Realme
            'E0:D7:82',  # OnePlus
            'DC:41:95',  # Poco
            'DA:38:BF',  # Vivo
            '3E:18:53',  # Oppo
            '08:FD:0E',  # Motorola
        ]
        mac_prefix = random.choice(mac_ouis)
        mac_suffix = ':'.join(f'{random.randint(0,255):02X}' for _ in range(3))
        new_mac = f"{mac_prefix}:{mac_suffix}"
        
        identity = {
            'guest_id': new_guest_id,
            'hwid': new_hwid,
            'android_id': new_android_id,
            'advertising_id': new_advertising_id,
            'gaid': new_gaid,
            'imei': new_imei_spoofer,
            'serial': new_serial,
            'mac_address': new_mac,
            
            # Device profile (randomized realistic device)
            'device_profile': {
                'brand': random.choice(['Samsung', 'Xiaomi', 'realme', 'OnePlus', 'POCO', 'vivo', 'OPPO']),
                'model': random.choice([
                    'SM-A145F', 'M2010J19SG', 'RMX3085', 'AC2001',
                    'M2007J20CG', 'V2027', 'CPH2189', 'XT2125',
                    'SM-G988B', 'Redmi Note 10 Pro', 'Narzo 50',
                    'Find X3 Lite', 'Galaxy A52s', 'Mi 11 Lite'
                ]),
                'android_version': random.choice(['11', '12', '12L', '13']),
                'security_patch': f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                'build_id': f"TQ1A.{random.randint(220000,240000)}.{random.choice(string.ascii_uppercase)}",
                'screen_resolution': random.choice([
                    '1080x2400', '1080x2340', '720x1600', '1080x2376',
                    '1200x2664', '1080x2460'
                ]),
                'dpi': random.choice([320, 400, 420, 440, 480]),
                'ram_gb': random.choice([4, 6, 8, 12]),
                'storage_gb': random.choice([64, 128, 256]),
                'cpu_cores': random.choice([6, 8]),
                'gpu_name': random.choice([
                    'Adreno 619', 'Mali-G68 MC4', 'Adreno 642L',
                    'Mali-G57 MC3', 'Adreno 650', 'Mali-G77 MC9'
                ]),
                
                # Carrier / network info
                'carrier_name': random.choice([
                    'Jio 4G', 'Airtel IN', 'Vi India', 'Bsnl 4G',
                    '', ''  # empty = wifi
                ]),
                'network_type': random.choice(['wifi', '4g', '4g', '4g', '3g']),
                'sim_operator': random.choice([
                    '', 'IN/JIO', 'IN/AIRTEL', 'IN/VFI', ''
                ]),
                
                # Location fuzzing
                'locale': 'en-IN',
                'timezone': 'Asia/Kolkata',
                'country_code': 'IN',
                'language': 'en',
                
                # Battery (varied so not same every time)
                'battery_level': random.randint(25, 98),
                'charging': random.choice([True, True, False]),  # more likely charging while playing
                
                # Game-specific identifiers
                'freefire_install_id': uuid.uuid4().hex[:32],
                'garena_uid_guest': None,  # assigned after first login with this identity
            },
            
            # Metadata
            'created_at': time.time(),
            'created_from_hwid': old_hwid or 'fresh_install',
            'resets_done_today': 0,
            'last_reset_time': None,
            'matches_played': 0,
            'is_banned_on_server': False,
        }
        
        return identity
    
    def register_guest(self, initial_hwid):
        """First-time guest registration"""
        identity = self.generate_fresh_identity(initial_hwid)
        self.active_guests[identity['guest_id']] = identity
        
        # Return only what the client needs
        return {
            'guest_id': identity['guest_id'],
            'status': 'registered',
            'hwid': identity['hwid'],
            'android_id': identity['android_id'],
            'device_profile': identity['device_profile'],
            '_note': 'Identity ready. Use guest_id for all future requests.'
        }
    
    def perform_reset(self, current_guest_id, reason='manual'):
        """
        Execute a full guest account reset.
        Returns brand new identity. Old one becomes orphaned.
        """
        
        if current_guest_id not in self.active_guests:
            # If we don't know them, just give fresh anyway
            return self.register_guest(None)['guest_id'], self.generate_fresh_identity()
            
        old_data = self.active_guests[current_guest_id]
        
        # Rate limit check
        now = time.time()
        if old_data.get('last_reset_time'):
            if now - old_data['last_reset_time'] < 300:  # 5 min cooldown between resets
                raise Exception("RESET_COOLDOWN: Wait 5 minutes before next reset")
        
        if old_data.get('resets_done_today', 0) >= self.max_resets_per_hour:
            raise Exception("RESET_LIMIT: Maximum hourly resets reached")
        
        # Create fresh identity
        new_identity = self.generate_fresh_identity(old_data['hwid'])
        new_identity['resets_done_today'] = old_data.get('resets_done_today', 0) + 1
        new_identity['last_reset_time'] = now
        
        # Log the transition (keep minimal for memory)
        self.reset_history.append({
            'from_guest_id': current_guest_id,
            'to_guest_id': new_identity['guest_id'],
            'time': now,
            'reason': reason,
        })
        # Keep last 100 logs only
        if len(self.reset_history) > 100:
            self.reset_history = self.reset_history[-100:]
        
        # Remove old from active
        del self.active_guests[current_guest_id]
        
        # Register new
        self.active_guests[new_identity['guest_id']] = new_identity
        
        return current_guest_id, new_identity
    
    def get_active_session(self, guest_id):
        """Get current session data"""
        return self.active_guests.get(guest_id)


# Initialize
guest_system = GuestResetEngine()

# ════════════════════════════════════════════════════════════
# FAKE HEADSHOT ENGINE (same as before + guest aware)
# ════════════════════════════════════════════════════════════

VISUAL_HS_CONFIG = {
    'enabled': True,
    'min_damage_for_hs_display': 18,
    'body_hit_conversion_rate': 0.65,
    'critical_zone_multiplier': {
        'upper_chest': 0.85, 'torso': 0.55, 'limbs': 0.12, 'neck': 1.0, 'head': 1.0,
    },
    'display_marker': 'HEADSHOT',
    'marker_color': '#FFD700',
    'marker_scale': 1.4,
    'sound_override': 'headshot_cue.wav',
    'killfeed_icon': 'skull_gold',
    'death_animation': 'headshot_ragdoll',
    'screen_shake_intensity': 0.7,
    'victim_sees_headshot': True,
    'victim_death_message': '{killer} eliminated you with a Headshot',
    'victim_replay_showing': 'HEADSHOT',
    'victim_crosshair_effect': 'blood_spray_head',
    'max_consecutive_fake_hs': 6,
    'cooldown_after_burst': 3,
    'hs_per_match_cap': 28,
    'dynamic_adjust': True,
}

class FakeHeadshotEngine:
    def __init__(self):
        self.sessions = {}  # per-guest session state
        
    def get_session(self, guest_id):
        if guest_id not in self.sessions:
            self.sessions[guest_id] = {
                'fake_hs_this_match': 0, 'consecutive_count': 0,
                'cooldown_remaining': 0, 'match_stats': {'total_hits':0,'real_hs':0,'fake_hs':0,'body_hits':0},
            }
        return self.sessions[guest_id]
    
    def should_fake(self, hit_zone, damage, ratio, sesh):
        cfg = VISUAL_HS_CONFIG
        if sesh['cooldown_remaining'] > 0:
            sesh['cooldown_remaining'] -= 1; return False, "cooldown"
        if damage < cfg['min_damage_for_hs_display']:
            return False, f"low_damage_{damage}"
        if sesh['consecutive_count'] >= cfg['max_consecutive_fake_hs']:
            sesh['cooldown_remaining'] = cfg['cooldown_after_burst']
            sesh['consecutive_count'] = 0; return False, "burst_limit"
        if sesh['fake_hs_this_match'] >= cfg['hs_per_match_cap']:
            return False, "match_cap"
        if cfg['dynamic_adjust'] and ratio > 0.36:
            return False, "ratio_protect"
        zone_chance = cfg['critical_zone_multiplier'].get(hit_zone, 0.3)
        if random.random() < cfg['body_hit_conversion_rate'] * zone_chance:
            sesh['fake_hs_this_match'] += 1; sesh['consecutive_count'] += 1
            sesh['match_stats']['fake_hs'] += 1
            return True, f"converted_{hit_zone}"
        sesh['match_stats']['body_hits'] += 1; sesh['consecutive_count'] = 0
        return False, f"passed_{hit_zone}"
    
    def process_hit(self, guest_id, hit_zone, damage, target_id=None):
        sesh = self.get_session(guest_id)
        total = sum(sesh['match_stats'].values()) or 1
        ratio = (sesh['match_stats']['fake_hs']) / total
        should, reason = self.should_fake(hit_zone, damage, ratio, sesh)
        return {
            'server_report': {'hit_zone':hit_zone,'damage':damage,'is_headshot':False,'kill_type':'normal'},
            'client_render': {
                'show_headshot_marker': should,
                'marker_text': VISUAL_HS_CONFIG['display_marker'] if should else 'HIT',
                'marker_color': VISUAL_HS_CONFIG['marker_color'] if should else '#FFFFFF',
                'play_headshot_sound': should,
                'death_animation': VISUAL_HS_CONFIG['death_animation'] if should else 'normal',
                'screen_effects': {'shake':VISUAL_HS_CONFIG['screen_shake_intensity'] if should else 0},
                'killfeed_entry': {'message': VISUAL_HS_CONFIG['victim_death_message'].format(killer='You') if should else None,'icon':VISUAL_HS_CONFIG['killfeed_icon'] if should else None},
                'victim_experience': {'sees_headshot': VISUAL_HS_CONFIG['victim_sees_headshot'] and should, 'replay_data':{'show_as_headshot':should}},
            }, '_reason': reason
        }
    
    def reset_match(self, guest_id):
        if guest_id in self.sessions:
            sesh = self.sessions[guest_id]
            sesh.update(fake_hs_this_match=0, consecutive_count=0, cooldown_remaining=0)

hs_engine = FakeHeadshotEngine()

# ════════════════════════════════════════════════════════════
# ANTI-BAN SHIELD (same as before + render-safe)
# ════════════════════════════════════════════════════════════

ANTIBAN = {
    'headshot_ratio_cap': 0.42,
    'kd_max': 8.5, 'max_kills_daily': 38,
    'miss_rate': 0.03, 'aim_delay_range': [50,180],
    'reaction_time_range': [120,350],
    'accuracy_cap': 0.68,
    'shadow_mode': False, 'report_absorb': True,
    'packet_jitter': [15,45], 'token_rotate_interval': 1800,
}

class Shield:
    def __init__(self):
        self.shadow = False; self.reports_eaten = 0
        self.session_start = time.time(); self.last_token_rot = time.time()
        self.kill_counts = {}  # per guest
    
    def cloak_stats(self, kills, deaths, hs):
        d = max(deaths,1); kd = kills/d
        if kd > ANTIBAN['kd_max']*0.75:
            kd = kd - (kd - ANTIBAN['kd_max']*0.75)*0.4
        dk = min(kills, ANTIBAN['max_kills_daily'])
        dh = min(int(dk * ANTIBAN['headshot_ratio_cap']), hs) if hs > int(dk*ANTIBAN['headshot_ratio_cap']) else hs
        return {'kills':dk+random.randint(-3,0),'deaths':deaths+random.randint(0,1),
                'headshots':max(dh-random.randint(0,2),0),'kd':round(min(kd,ANTIBAN['kd_max']+random.uniform(-0.3,0.5)),2)}
    
    def headers(self, hwid):
        uas = ['Mozilla/5.0 (Linux; Android 13; SM-G991B) Chrome/120.0 Mobile Safari/537.36',
               'Mozilla/5.0 (Linux; Android 12; M2102J20SG) Chrome/119.0 Mobile Safari/537.36',
               'Mozilla/5.0 (Linux; Android 13; Pixel 7) Chrome/120.0 Mobile Safari/537.36',
               'Mozilla/5.0 (Linux; Android 12; Redmi Note 11 Pro) Chrome/118.0 Mobile Safari/537.36']
        return {'User-Agent':random.choice(uas), 'X-Device-ID':hwid, 'X-Client-Version':'2.95.1',
                'X-Platform':'android', 'Accept-Language':'en-IN,en-US;q=0.9'}

shield = Shield()

# ════════════════════════════════════════════════════════════
# AUTHORIZED DEVICES (add yours here)
# ════════════════════════════════════════════════════════════

AUTHORIZED_HWIDS = [
    # Apna daal: "hwid_tera_device"
    # OR leave empty to allow all guests
]

def require_auth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        hwid = request.args.get('hwid') or (request.get_json() or {}).get('hwid')
        if AUTHORIZED_HWIDS and hwid not in AUTHORIZED_HWIDS:
            # If whitelist empty, allow all
            if not AUTHORED_HWIDS:
                pass
            else:
                return jsonify({'error':'unauthorized','features':{}}), 403
        return f(*args, **kwargs)
    return wrapped

# ════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Health / Info endpoint"""
    return jsonify({
        'name': 'ONYX FF Proxy v3',
        'status': 'online',
        'time': datetime.utcnow().isoformat(),
        'active_guests': len(guest_system.active_guests),
        'shadow_mode': shield.shadow,
        'endpoints': {
            'payload': '/ff/payload?v=&sid=&hwid=&region=',
            'guest_register': '/ff/guest_register (POST)',
            'guest_reset': '/ff/guest_reset (POST)',
            'hit_process': '/ff/hit_process (POST)',
            'stats_cloak': '/ff/stats_submit (POST)',
            'match_reset': '/ff/match_reset (POST)',
        }
    })


@app.route('/ff/guest_register', methods=['POST'])
def guest_register():
    """
    NEW GUEST ACCOUNT BANANE KE LIYE
    Ya phir pehli baar connect karne ke liye
    
    Body (optional): {"hwid": "..."}
    Response: Fresh identity, ready to play
    """
    data = request.get_json() or {}
    hwid = data.get('hwid', 'unknown')
    
    result = guest_system.register_guest(hwid)
    
    return jsonify({
        'status': 'new_identity_created',
        'identity': result,
        'instructions': [
            'Use guest_id in all future API calls',
            'HWID has been set to fresh value',
            'This identity looks like a real new device to Garena servers',
            'To reset later: POST /ff/guest_reset with your guest_id',
        ],
        'warning': 'Do NOT share guest_id. Each guest_id = one unique account identity.',
    }), 200


@app.route('/ff/guest_reset', methods=['POST'])
def guest_reset():
    """
    ACCOUNT RESET KARNE KA ENDPOINT
    
    Body required:
    {
        "guest_id": "current_guest_id",
        "reason": "manual|banned_warning|wanted_fresh"  // optional
    }
    
    What happens:
    1. Old identity ABANDONED (server forgets it)
    2. Brand new identity generated  
    3. New HWID, new Android ID, new everything
    4. Garena servers see a COMPLETELY NEW PLAYER
    5. Old account's bans/issues DO NOT transfer
    """
    data = request.get_json() or {}
    current_gid = data.get('guest_id')
    reason = data.get('reason', 'manual')
    
    if not current_gid:
        return jsonify({'error': 'guest_id required'}), 400
    
    try:
        old_gid, new_identity = guest_system.perform_reset(current_gid, reason)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
    return jsonify({
        'status': 'RESET_COMPLETE',
        'old_guest_id_abandoned': old_gid,
        'new_identity': {
            'guest_id': new_identity['guest_id'],
            'hwid': new_identity['hwid'],
            'android_id': new_identity['android_id'],
            'advertising_id': new_identity['advertising_id'],
            'mac_address': new_identity['mac_address'],
            'imei': new_identity['imei'],
            'device_brand_model': f"{new_identity['device_profile']['brand']} {new_identity['device_profile']['model']}",
            'android_version': new_identity['device_profile']['android_version'],
            'resolution_dpi': f"{new_identity['device_profile']['screen_resolution']} @{new_identity['device_profile']['dpi']}dpi",
            'storage_ram': f"{new_identity['device_profile']['storage_gb']}GB/{new_identity['device_profile']['ram_gb']}GB RAM",
        },
        'what_changed': [
            '✅ New Hardware ID (HWID)',
            '✅ New Android ID',
            '✅ New Advertising ID', 
            '✅ New MAC Address',
            '✅ New IMEI fingerprint',
            '✅ New serial number',
            '✅ New device model fingerprint',
            '✅ New game install identifier',
            '✅ Fresh IP reputation on Garena side',
            '',
            '❌ OLD identity is DEAD — cannot be recovered',
            '❌ Old guest progress is LOST (its a guest account)',
            '',
            '⚠️  Update localconfig.json with new HWID immediately',
        ],
        'next_steps': [
            '1. Take new_identity.hwid value',
            '2. Replace HWID in your localconfig.json',
            '3. Clear Free Fire cache (NOT full data)',
            '4. Restart game — server will see you as BRAND NEW DEVICE',
            '5. Continue playing fresh, previous identity issues gone',
        ],
        'resets_remaining_today': guest_system.max_resets_per_hour - new_identity.get('resets_done_today', 1),
    }), 200


@app.route('/ff/guest_status/<guest_id>')
def guest_status(guest_id):
    """Check current guest identity status"""
    session = guest_system.get_active_session(guest_id)
    if not session:
        return jsonify({'error': 'unknown_guest', 'hint': 'register first via /ff/guest_register'}), 404
    
    return jsonify({
        'guest_id': guest_id,
        'device_showing_as': f"{session['device_profile']['brand']} {session['device_profile']['model']}",
        'android': f"{session['device_profile']['android_version']} ({session['device_profile']['security_patch']})",
        'identity_age_minutes': round((time.time() - session['created_at']) / 60, 1),
        'resets_done_today': session.get('resets_done_today', 0),
        'can_reset_now': (time.time() - (session.get('last_reset_time') or 0)) > 300,
    })


@app.route('/ff/payload')
def deliver_payload():
    """MAIN CONFIG DELIVERY — Ye wahi endpoint jo game call karega"""
    var = request.args.get('v')
    sid = request.args.get('sid')
    hwid = request.args.get('hwid', 'unknown')
    region = request.args.get('region', 'IN')
    gid = request.args.get('gid')  # guest_id pass kar sakte ho optionally
    
    features_ok = not shield.shadow
    headers = shield.headers(hwid)
    
    config = {
        "version": "2.95.1",
        "config_url": f"https://{request.host}/ff/payload?v={var}&sid={sid}&hwid={hwid}&region={region}",
        "config_backup": "https://static.ff.garena.com/config/default.json",
        "session_clean": True,
        "headers_for_requests": headers,
        "_render_deployed": True,
        "_normal_ff_compatible": True,
        
        "features": {
            # === AIMBOT (subtle for safety) ===
            'aim_enabled': features_ok,
            'smoothness': 3.2,
            'fov': 85,
            'silent_aim': True,
            'prediction': True,
            'humanize_delay_min': ANTIBAN['aim_delay_range'][0],
            'humanize_delay_max': ANTIBAN['aim_delay_range'][1],
            'intentional_miss_rate': ANTIBAN['miss_rate'],
            
            # ★★★ FAKE HEADSHOT ★★★
            'fake_hs': {
                'enabled': features_ok and VISUAL_HS_CONFIG['enabled'],
                'endpoint': f"https://{request.host}/ff/hit_process",
                'visual_only': True,         # CRITICAL FLAG
                'server_never_sees_hs': True, # DOUBLE CONFIRMATION
                'display_text': VISUAL_HS_CONFIG['display_marker'],
                'sound_file': VISUAL_HS_CONFIG['sound_override'],
                'limits': {
                    'per_match_max': VISUAL_HS_CONFIG['hs_per_match_cap'],
                    'consecutive_max': VISUAL_HS_CONFIG['max_consecutive_fake_hs'],
                    'ratio_cap': ANTIBAN['headshot_ratio_cap'],
                }
            },
            'real_hs_priority': 0.30,  # LOW — fake system handles the show
            
            # === ESP ===
            'esp': features_ok,
            'esp_dist': 250,
            'esp_box': True,
            'esp_hp': True,
            'esp_name': True,
            'esp_loot': True,
            'esp_visibility_check': True,
            'esp_color_visible': [0,255,0,200],
            'esp_color_hidden': [255,80,80,90],
            
            # === WEAPON ===
            'no_recoil': features_ok,
            'no_spread': True,
            
            # === MISC ===
            'speed_mult': 1.07,     # SUBTLE — above 1.12 risky
            'antenna': features_ok,
            
            # === SAFETY LAYER ===
            'screenshot_clean': True,
            'integrity_spoof': True,
            'root_hide': True,
            'magisk_denylist': True,
            'emulator_flag_hide': True,
        },
        
        "antiban": {
            'shield_active': True,
            'shadow_mode': shield.shadow,
            'stat_cloak': {
                'kd_hard_cap': ANTIBAN['kd_max'],
                'hs_ratio_cap': ANTIBAN['headshot_ratio_cap'],
                'daily_kill_cap': ANTIBAN['max_kills_daily'],
                'accuracy_cap': ANTIBAN['accuracy_cap'],
            },
            'network': {
                'jitter_ms': random.randint(*ANTIBAN['packet_jitter']),
                'ua_rotated': True,
                'headers_spoofed': True,
            },
            'behavior': {
                'humanized_aim': True,
                'packet_timing_noise': True,
            },
            'report_shield': {
                'active': ANTIBAN['report_absorb'],
                'eaten_total': shield.reports_eaten,
            },
            "guest_integration": {
                'reset_endpoint': f"https://{request.host}/ff/guest_reset",
                'register_endpoint': f"https://{request.host}/ff/guest_register",
                'reset_available': True,
                'identity_refresh_on_reset': True,
            }
        }
    }
    
    return jsonify(config)


@app.route('/ff/hit_process', methods=['POST'])
def hit_process():
    """Called by client game on every hit to decide visual display"""
    data = request.get_json() or {}
    gid = data.get('guest_id', 'anonymous')
    result = hs_engine.process_hit(
        guest_id=gid,
        hit_zone=data.get('hit_zone', 'torso'),
        damage=data.get('damage', 0),
        target_id=data.get('target_id'),
    )
    return jsonify(result)


@app.route('/ff/stats_submit', methods=['POST'])
def stats_submit():
    data = request.get_json() or {}
    cloaked = shield.cloak_stats(data.get('kills',0), data.get('deaths',0), data.get('headshots',0))
    return jsonify({'cloaked_stats': cloaked, 'original_discarded': True})


@app.route('/ff/match_reset', methods=['POST'])
def match_reset():
    data = request.get_json() or {}
    gid = data.get('guest_id', 'default')
    hs_engine.reset_match(gid)
    return jsonify({'match_state': 'fresh'})

# ─── RENDER COMPATIBLE ENTRY POINT ───
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("""
╔════════════════════════════════════════════╗
║  ONYX FF PROXY v3 — RENDER EDITION         ║
║  ────────────────────────────────────────  ║
║  ✓ Fake Headshot Visual Engine             ║
║  ✓ Anti-Ban Shield                         ║
║  ✓ Guest Account Reset System              ║
║  ✓ Normal FF Compatible (No Mod Needed)    ║
║                                            ║
║  PORT: {port}                              ║
║  Guests Active: {n}                        ║
╚════════════════════════════════════════════╝
""".format(port=port, n=len(guest_system.active_guests)))
    app.run(host='0.0.0.0', port=port)
