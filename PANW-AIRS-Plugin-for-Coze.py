from runtime import Args
from typings.PANW_AI_Security.PANW_AI_Security import Input, Output
import requests

AIRS_API_URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"

"""
Each file needs to export a function named `handler`. This function is the entrance to the Tool.

Parameters:
args: parameters of the entry function.
args.input - input parameters, you can get test input value by args.input.xxx.
args.logger - logger instance used to print logs, injected by runtime.

Remember to fill in input/output in Metadata, it helps LLM to recognize and use tool.

Return:
The return data of the function, which should match the declared output parameters.
"""
def handler(args: Args[Input]) -> Output:
    # Get credentials from runtime
    airs_api_key = args.input.PANW_AIRS_API_key
    airs_ai_profile_name = args.input.PANW_AIRS_Profile_Name

    headers = {
        "Content-Type": "application/json",
        "x-pan-token": airs_api_key
    }

    contents = {}
    if args.input.InputorOutputCheck == "input":
        contents["prompt"] = args.input.Query
    else: 
        contents["response"] = args.input.Query

    data = {
        "metadata": {
            "ai_model": args.input.Model,
            "app_name": args.input.AppName,
            "app_user": args.input.AppUser
        },
        "contents": [contents],
        "ai_profile": {
            "profile_name": airs_ai_profile_name
        }
    }
    action = 'allow'  # 如果执行过程遇到异常，为了保障应用的正常运行，默认为 allow，管理员也可以改成默认 block

    response = requests.post(AIRS_API_URL, headers=headers, json=data, verify=False)
    if response.status_code == 200:
        valuable_res = response.json()
        action= valuable_res["action"]
        args.logger.info("API Result: " + valuable_res.get("action", ""))
    ret: Output = {
        "action": action,
        "result": valuable_res

    }
    return ret
