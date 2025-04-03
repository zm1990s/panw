import requests
import json

def main(input: str) -> dict:
    token = 'token'
    profile_name = "matt"
    user_input = input
    ai_model = "Model"
    app_name = "test"
    app_user = "test"
    inputoroutput = "output"
    action = "allow"  # 默认动作，如果执行过程中遇到异常，为了保障应用的正常运行，默认为 allow，管理员也可以改成默认 block

    # Ensure the URL is correctly formatted
    url = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
    headers = {"x-pan-token": token, "Content-Type": "application/json"}

    contents = {}
    if inputoroutput == "input":
        contents["prompt"] = user_input
    elif inputoroutput == "output":
        contents["response"] = user_input

    data = {
        "metadata": {
            "ai_model": ai_model,
            "app_name": app_name,
            "app_user": app_user
        },
        "contents": [contents],
        "ai_profile": {
            "profile_name": profile_name
        }
    }

    json_data = json.dumps(data)

    try:
        response = requests.post(url, data=json_data, headers=headers)
        response.raise_for_status()  # 检查响应状态码是否为 200

        if response.status_code == 200:
            response_data = response.json()
            action = response_data.get('action', action)
            dlp = str(response_data.get("response_detected", {}).get("dlp", ""))
            db_security = str(response_data.get("response_detected", {}).get("db_security", ""))
            url_cats = str(response_data.get("response_detected", {}).get("url_cats", ""))
            toxic_content = str(response_data.get("response_detected", {}).get("toxic_content", ""))
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        action = "block"  # Set a default action in case of failure
    
    # 返回提取的变量
    return {
        "action": action,
        "dlp": dlp,
        "db_security": db_security,
        "url_cats": url_cats,
        "toxic_content": toxic_content
    }
