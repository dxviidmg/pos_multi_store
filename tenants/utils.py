import requests
from django.conf import settings

def render_redeploy():
    url = f"https://api.render.com/v1/services/{settings.RENDER_SERVICE_ID}/deploys"

    headers = {
        "Authorization": f"Bearer {settings.RENDER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            headers=headers,
        )

        response.raise_for_status()  # lanza excepción si no es 2xx

        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json(),
        }

    except requests.Timeout:
        return {"success": False, "error": "Request timeout"}

    except requests.HTTPError as e:
        return {
            "success": False,
            "status_code": e.response.status_code,
            "error": e.response.text,
        }

    except requests.RequestException as e:
        return {"success": False, "error": str(e)}
