import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SleepNotificationTool:
    """Custom tool to send sleep intervention notifications via Cloud Function."""

    def __init__(self, cloud_function_url: str):
        self.cloud_function_url = cloud_function_url

    def send_notification(
        self,
        user_id: str,
        intervention_id: int,
        title: str,
        body: str,
        intervention_type: str
    ) -> Dict[str, Any]:
        """
        Send a push notification for a sleep intervention.

        Args:
            user_id: User's unique identifier
            intervention_id: Database ID of the intervention
            title: Notification title
            body: Notification body text
            intervention_type: Type of intervention

        Returns:
            Response from the Cloud Function (or an error dict).
        """
        payload = {
            "user_id": user_id,
            "intervention_id": intervention_id,
            "title": title,
            "body": body,
            "intervention_type": intervention_type
        }

        try:
            response = requests.post(
                self.cloud_function_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Notification sent successfully: {result}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return {"error": str(e), "success": False}
