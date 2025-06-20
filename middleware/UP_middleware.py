# pip install pywebpush cryptography
from flask import Flask, request, jsonify, Response
import requests
import redis
import os
import json
import sqlite3

## for VAPID
from pywebpush import webpush, WebPushException
vapid_private_key = os.getenv("vapid_private_key", "")
vapid_public_key = os.getenv("vapid_public_key", "")
TOPIC_TOKEN = os.getenv("NTFY_AUTH_TOKEN", "")
VAPID_DB_PATH = os.getenv("VAPID_DB_PATH", "/var/cache/ntfy/webpush.db")

# Connect to Redis (Docker-based, default settings) to store the user ->UnifiedPush topic etc
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

## where is RC?
ROCKETCHAT_URL =  os.getenv("ROCKETCHAT_URL", "http://localhost:3000")

app = Flask(__name__)

#################################
# # === FUNCTION: Load VAPID subscriptions from the database ===
def get_subscriptions(db_path, topic_filter=None):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = "SELECT endpoint, p256dh, auth, topic FROM subscriptions"
    params = ()
    if topic_filter:
        query += " WHERE topic = ?"
        params = (topic_filter,)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    subscriptions = []
    for endpoint, p256dh, auth, topic in rows:
        subscriptions.append({
            "endpoint": endpoint,
            "keys": {
                "p256dh": p256dh,
                "auth": auth
            },
            "topic": topic
        })
    return subscriptions


# # === FUNCTION: Send encrypted push ===
def send_push(sub, payload):
    try:
        response = webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": sub["keys"]
            },
            data=payload,
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": VAPID_EMAIL}
        )
        print(f"✅ Sent to {sub['endpoint']} (topic: {sub['topic']})")
    except WebPushException as ex:
        print(f"❌ error {sub['endpoint']}: {repr(ex)}")


def is_authenticated_RC(user_id, auth_token):
    """
    validate the user's RC credentials are correct. if not they should not be able to get anything 
    """
    headers = {"X-User-Id":user_id, "X-Auth-Token":auth_token}
    try:
        print(f"{ROCKETCHAT_URL}/api/v1/me", user_id)
        response = requests.get(f"{ROCKETCHAT_URL}/api/v1/me", headers=headers)
        # print('is_authenticated_RC()', response.content)
        return response.status_code == 200 and response.json().get("success", False)
    except Exception as e:
        print('RC auth error', e)
        return False


@app.route("/register/<topic>", defaults={'format': None}, methods=["GET"])
@app.route("/register/<topic>/<format>", methods=["GET"])
def register(topic, format):
    '''
    proxy for topic registration - per GHF request
    '''
    print(topic, dict(request.args), dict(request.headers))
    if topic is None:
        return jsonify({"error": "Topic parameter is missing"}), 400
    base_url = f"http://localhost:8081/register/{topic}"
    since = request.args.get('since')
    if since == 'none':
        # You can choose to ignore it or handle it specifically
        pass
    print(jsonify({
        "headers": dict(request.headers),
        "args": dict(request.args),
        "topic": topic,
        "format": format
    }))
    try:
        headers = {key: value for key, value in request.headers if key.lower() != 'host'}
        resp = requests.get(base_url, headers=headers, params=request.args)
        return Response(
            resp.content,
            status=resp.status_code,
            headers=dict(resp.headers)
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 502


@app.route("/register", methods=["POST"])
def register_post():
    print(request)
    print(request.headers)
    data = request.json
    print("POSTED: ", data)
    up_endpoint = data['UP_push_server']
    up_endpoint = up_endpoint.split('?')[0]
    # topic = up_endpoint.split('/')[-1]
    topic = up_endpoint
    ## as discussed with Jon we need to keep the entire URL in case the customer is using a foriegn gateway
    user_id = request.headers.get("x-user-id")
    user_token = data.get("userToken")
    if not user_id:
        user_id = data.get("userId")
    if not user_token:
        user_token = request.headers.get("x-auth-token")
    if is_authenticated_RC(user_id, user_token):
        print(f'USER VALID- {user_id}')
        redis_client.set(user_id, topic)
        return jsonify({"status":"success", "authenticated": False}), 200
    return jsonify({"error": "Missing user_id or topic"}), 500


@app.route("/vapidPublicKey", methods=["GET"])
def vapid_public_key():
    return jsonify({"webpush-public-key": vapid_public_key}), 200

@app.route("/authenticate", methods=["GET"])
def up_authenticate():
    ''' for LDAP over of NTFY '''
    return render_template("topic_auth.html")


@app.route("/rocket-webhook-public-channels", methods=["POST"])
def rocket_webhook_public_channel():
    data = request.json
    # print(data)
    return jsonify({"message": "Notification sent"}), 200

@app.route("/rocket-webhook-private-groups", methods=["POST"])
def rocket_webhook_private_groups():
    data = request.json
    print(data)
    return jsonify({"message": "Notification sent"}), 200

@app.route("/rocket-webhook-direct", methods=["POST"])
def rocket_webhook_direct():
    data = request.json
    # print(data)
    channel_id = data['channel_id']
    user_id = data['user_id']
    timestamp = data['timestamp']
    user_name = data['user_name']
    message_id = data['message_id']
    message = data.get("text")
    site_url = data.get("siteUrl")
    reciever = ''
    if not timestamp or not message:
        return jsonify({"error": "Invalid payload"}), 400
    if channel_id.startswith(user_id):
        reciever = channel_id.lstrip(user_id)
    else:
        reciever = channel_id.rstrip(user_id)
    # print(f'message {user_id} -> {reciever} ')
    # user = data.get(user_id, {}).get("username")
    endpoint = redis_client.get(reciever)
    # print(f'"{reciever}"  is registered to "{endpoint}"')
    if not endpoint:
        return jsonify({"error": "No endpoint registered for user"}), 404
    payload = {
        "message": f"New message from {user_id}: {message}"
    }
    # type {GROUP:p, DIRECT:d, CHANNEL:c}
    payload = {"message": message,  "decrypted": "true", 
    # "channel_id":channel_id, "message_id": message_id,
     "user_name":user_name, "timestamp": timestamp,
    "host":site_url, "type": "d", "rid":channel_id,
    "url":"rocketchat://host=%s?rid=%s" % (site_url.lstrip("https://").lstrip("http://"), channel_id)}
    try:
        # print(payload)
        headers={ "Content-Type" : "application/json" }
        if site_url in endpoint:
            headers["Authorization"] = f"Basic {TOPIC_TOKEN}"
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return jsonify({"message": "Notification sent"}), 200
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/UP_PROXY", methods=["POST"])
def up_proxy_ntfy():
    data = request.json
    print('up_proxy_ntfy', data)
    return jsonify({"message": "Notification sent"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5001)
