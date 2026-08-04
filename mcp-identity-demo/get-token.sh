# 先在终端拿 token
curl -s -X POST "https://dev-u3pos145gov1nqu3.us.auth0.com/oauth/token" \
  -H "content-type: application/json" \
  -d "{\"client_id\":\"$AUTH0_CLIENT_ID\",\"client_secret\":\"$AUTH0_CLIENT_SECRET\",\"audience\":\"$AUTH0_AUDIENCE\",\"grant_type\":\"client_credentials\"}" | jq .