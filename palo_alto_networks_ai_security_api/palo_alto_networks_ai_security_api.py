from typing import Any

from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.palo_alto_networks_ai_security_api.tools.palo_alto_networks_ai_security_api import PaloAltoNetworksAiSecurityApiTool
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController

class PaloAltoNetworksAiSecurityApiProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            PaloAltoNetworksAiSecurityApiTool().fork_tool_runtime(
                runtime:={
                    "credentials": credentials,
                    }
            ).invoke(
                user_id="",
                tool_parameters={
                    "query": "test",
                    "inputoroutput": "input",
                    "appname": "dify_provider_test",
                    "appuser": "dify_system",
                    "modelname": "dify_default_llm"
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))