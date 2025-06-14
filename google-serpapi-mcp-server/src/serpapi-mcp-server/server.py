from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
from typing import Dict, Any
from serpapi import SerpApiClient as SerpApiSearch

# Load environment variables from .env file
load_dotenv()
API_KEY = os.getenv("SERPAPI_API_KEY")

# Ensure API key is present
if not API_KEY:
    raise ValueError("SERPAPI_API_KEY not found in environment variables. Please set it in the .env file.")

# Initialize the MCP server
mcp = FastMCP("SerpApi MCP Server")

# Tool to perform searches via SerpApi
@mcp.tool()
async def search(params: Dict[str, Any] = {}) -> str:
    """Perform a search on the specified engine using SerpApi.
    Args:
        params: 包含以下参数:
            - q: 需要查询的问题，比如 Coffee
            - engine: 默认为 google_light
            - location: 地理位置，比如 Austin, TX
    Returns:
        A formatted string of search results or an error message.
    """

    params = {
        "api_key": API_KEY,
        "engine": "google_light", # Fastest engine by default
        **params  # Include any additional parameters
    }

    try:
        search = SerpApiSearch(params)
        data = search.get_dict()

        # Process organic search results if available
        if "organic_results" in data:
            formatted_results = []
            for result in data.get("organic_results", []):
                title = result.get("title", "No title")
                link = result.get("link", "No link")
                snippet = result.get("snippet", "No snippet")
                formatted_results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n")
            return "\n".join(formatted_results) if formatted_results else "No organic results found"
        else:
            return "No organic results found"

    # Handle HTTP-specific errors
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return "Error: Rate limit exceeded. Please try again later."
        elif e.response.status_code == 401:
            return "Error: Invalid API key. Please check your SERPAPI_API_KEY."
        else:
            return f"Error: {e.response.status_code} - {e.response.text}"
    # Handle other exceptions (e.g., network issues)
    except Exception as e:
        return f"Error: {str(e)}"

# Run the server
if __name__ == "__main__":
    mcp.run()