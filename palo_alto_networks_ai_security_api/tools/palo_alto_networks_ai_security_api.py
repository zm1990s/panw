from typing import Any, Union
from typing import Any

import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.tool.builtin_tool import BuiltinTool

AIRS_API_URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"

class PaloAltoNetworksAiSecurityApiTool(BuiltinTool):

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage:
        headers = {
            "Content-Type": "application/json",
            "x-pan-token": self.runtime.credentials["airs_api_key"]
        }

        contents = {}
        if tool_parameters.get("inputoroutput") == "input":
            contents["prompt"] = tool_parameters["query"]
        elif tool_parameters.get("inputoroutput") == "output":
            contents["response"] = tool_parameters["query"]
        # Determine the profile name based on the profileoverride parameter
        profileoverride = tool_parameters.get("profileoverride")
        if profileoverride:
            profile_name = profileoverride
        else:
            profile_name = self.runtime.credentials["airs_ai_profile_name"]

        data = {
            "metadata": {
                "ai_model": tool_parameters.get("modelname", "dify_default_llm"),
                "app_name": tool_parameters.get("appname", "dify_app"),
                "app_user": tool_parameters.get("appuser", "dify_user1")
            },
            "contents": [contents],
            "ai_profile": {
                "profile_name": profile_name
            }
        }

        response = requests.post(AIRS_API_URL, headers=headers, json=data, verify=False)
        response.raise_for_status()
        return self.create_text_message(response.json())