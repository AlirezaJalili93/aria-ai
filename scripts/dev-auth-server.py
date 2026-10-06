import http.server
import json
import time
from uuid import UUID
from cryptography.hazmat.primitives.asymmetric import ec
import jwt
from jwt.algorithms import ECAlgorithm

# Fixed deterministic EC key or ephemeral key
private_key = ec.generate_private_key(ec.SECP256R1())
public_key = private_key.public_key()
jwk_dict = ECAlgorithm.to_jwk(public_key, as_dict=True)
jwk_dict['kid'] = 'aria-dev-key'
jwk_dict['alg'] = 'ES256'
jwk_dict['use'] = 'sig'

JWKS_BYTES = json.dumps({'keys': [jwk_dict]}).encode('utf-8')
SEED_USER_ID = 'a0000000-0000-0000-0000-000000000001'
ISSUER = 'http://127.0.0.1:54321/auth/v1'

def make_session(email: str = 'owner@aria.local'):
    now = int(time.time())
    claims = {
        'sub': SEED_USER_ID,
        'aud': 'authenticated',
        'iss': ISSUER,
        'iat': now,
        'exp': now + 86400,
        'email': email,
        'role': 'authenticated'
    }
    token = jwt.encode(claims, private_key, algorithm='ES256', headers={'kid': 'aria-dev-key', 'alg': 'ES256'})
    return {
        'access_token': token,
        'token_type': 'bearer',
        'expires_in': 86400,
        'refresh_token': 'dev-refresh-token',
        'user': {
            'id': SEED_USER_ID,
            'aud': 'authenticated',
            'role': 'authenticated',
            'email': email,
            'app_metadata': {'provider': 'email'},
            'user_metadata': {'full_name': 'Aria Project Owner'}
        }
    }

class AuthHandler(http.server.BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', '*')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        if '/.well-known/jwks.json' in self.path:
            self.send_response(200)
            self._send_cors()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(JWKS_BYTES)))
            self.end_headers()
            self.wfile.write(JWKS_BYTES)
            return

        if '/user' in self.path:
            session = make_session()
            body = json.dumps(session['user']).encode('utf-8')
            self.send_response(200)
            self._send_cors()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            req_json = json.loads(post_data.decode('utf-8'))
        except Exception:
            req_json = {}

        email = req_json.get('email', 'owner@aria.local')

        if '/token' in self.path or '/signup' in self.path:
            session = make_session(email)
            body = json.dumps(session).encode('utf-8')
            self.send_response(200)
            self._send_cors()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if '/logout' in self.path or '/signout' in self.path:
            body = b'{}'
            self.send_response(200)
            self._send_cors()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        session = make_session(email)
        body = json.dumps(session).encode('utf-8')
        self.send_response(200)
        self._send_cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    server = http.server.HTTPServer(('127.0.0.1', 54321), AuthHandler)
    print('Dev Auth Server running on http://127.0.0.1:54321')
    server.serve_forever()
