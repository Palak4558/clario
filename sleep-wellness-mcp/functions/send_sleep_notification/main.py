import functions_framework
from firebase_admin import initialize_app, messaging, firestore
import json
from flask import jsonify

# Initialize Firebase Admin
initialize_app()
db = firestore.client()


@functions_framework.http
def send_sleep_notification(request):
    """
    HTTP Cloud Function to send sleep intervention notifications via FCM.

    Expected JSON payload:
    {
        "user_id": "user_123",
        "intervention_id": 42,
        "title": "Sleep Recommendation",
        "body": "Try going to bed 30 minutes earlier tonight...",
        "intervention_type": "sleep_schedule"
    }
    """
    try:
        request_json = request.get_json(silent=True)

        if not request_json:
            return jsonify({"error": "Invalid JSON payload"}), 400

        user_id = request_json.get('user_id')
        intervention_id = request_json.get('intervention_id')
        title = request_json.get('title', 'Sleep Recommendation')
        body = request_json.get('body')
        intervention_type = request_json.get('intervention_type', 'general')

        if not user_id or not body:
            return jsonify({"error": "Missing required fields: user_id, body"}), 400

        # Fetch user's FCM token from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({"error": f"User {user_id} not found"}), 404

        fcm_token = user_doc.to_dict().get('fcm_token')

        if not fcm_token:
            return jsonify({"error": f"No FCM token for user {user_id}"}), 400

        # Create FCM message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={
                'intervention_id': str(intervention_id),
                'intervention_type': intervention_type,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                'route': '/sleep-manager',  # Deep link to sleep manager screen
            },
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='ic_notification',
                    color='#4A90E2',
                    sound='default',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1,
                    ),
                ),
            ),
        )

        # Send notification
        response = messaging.send(message)

        # Store notification in Firestore for in-app display
        notification_ref = db.collection('users').document(user_id).collection('notifications').document()
        notification_ref.set({
            'title': title,
            'body': body,
            'intervention_id': intervention_id,
            'intervention_type': intervention_type,
            'read': False,
            'sent_at': firestore.SERVER_TIMESTAMP,
            'fcm_message_id': response,
        })

        return jsonify({
            "success": True,
            "message_id": response,
            "user_id": user_id,
            "intervention_id": intervention_id
        }), 200

    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return jsonify({"error": str(e)}), 500
