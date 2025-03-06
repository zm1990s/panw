def main(Query, PANW_AIRS_Profile_Name, PANW_AIRS_API_key, InputorOutputCheck):
    import requests, json
    AIRS_API_URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
    headers = {
      "Content-Type": "application/json",
      "x-pan-token": PANW_AIRS_API_key
    }
    contents = {}
    if InputorOutputCheck == "input":
        contents["prompt"] = Query
    else: 
        contents["response"] = Query
    data = {
        "metadata": {
            "ai_model": "MaxKB",
            "app_name": "MaxKB",
            "app_user": "MaxKB"
        },
        "contents": [contents],
        "ai_profile": {
            "profile_name": PANW_AIRS_Profile_Name
        }
    }
    response = requests.post(AIRS_API_URL, json = data, headers = headers)
    response_data = response.json()
    result = response_data.get('action')
#  return response_data
    return result