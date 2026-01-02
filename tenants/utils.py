import requests
from django.conf import settings

def render_redeploy():
    print(settings.RENDER_API_KEY, settings.RENDER_SERVICE_ID)
    url = "https://api.render.com/v1/services/"+ settings.RENDER_API_KEY + "/deploys"

    payload = {}
    headers = {
    'Authorization': 'Bearer ' +  settings.RENDER_SERVICE_ID
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        return response
    except requests.ConnectionError:
        return 'Connection Error'
    except Exception as e:
        print(e)
        return str(e)