curl -L -G "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/results" \
     -H 'Accept: application/json' \
     -H 'x-pan-token: <token>' \
     --data "scan_ids=fa56b59d-be3f-4140-b85a-2211e502cf5c" \
     -v