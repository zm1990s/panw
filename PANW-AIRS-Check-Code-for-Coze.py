import requests_async
import json
async def main(args: Args) -> Output:
    params = args.params
    token = params['X_PAN_TOKEN']
    profile_name = params['X_PAN_PROFILE_NAME']
    user_input = params['input']
    ai_model = params["AI_MODEL"]
    app_name = params['APP_NAME']
    app_user = params['APP_USER']
    inputoroutput = params['INPUTOUTPUT']
    action = 'allow'  # 如果执行过程遇到异常，为了保障应用的正常运行，默认为 allow，管理员也可以改成默认 block

    url = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
    headers = {"x-pan-token": token, "Content-Type":"application/json"}

    contents = {}
    if inputoroutput == "input":
        contents["prompt"] = user_input
    elif inputoroutput == "output":
        contents["response"] = user_input


    data = {
        "metadata":{
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

    response = await requests_async.post(url, data=json_data, headers=headers)
    
    if response.status_code == 200:
        response_data = response.json()
        action = response_data.get('action')

    ret: Output = {
        "pa_verdict": action
    }
    return ret