import urllib.request
import json

url = 'https://justrunmy.app/api/mcp'
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream',
    'X-User-Identity': 'CfDJ8I6qJxyfn1BFmLYpveog23+0uGkEKGu8zIvYfb9EPYJj+uUOtsrwEsppYLZPJp0+hZtoEoEMO+wCMmdmkS6wXf5xpht4cXkTizZMkS/JbGwYpfUh0+hmnB3TwTGSJTrude87xOmVYboTKSlZX6NqKOcIjGsfIHvKiiPlgxAeYQsgHcv3VyKqpVlw6bF4YoUgMjqLkX6C5LuaV65O2sd45CHqaPkA+Uqc38D3Ez1E3ocA4ymamG6rg/TXTW3xmM7X34B3ZwLW2OsFggNUptIS8IWbzsnFsOPwjFg73Wjf8ZpvK0shaU/j7vPjouMDfAUxQi4RUWDd75YHQQ6fB2VLOs9kIbZvfJWPxWwcSAfRYExWXRpwQEuYqRfFeFpXdMlF7efYW3GD3uwDTowNoD5effy4GUlso3LMRjb6i0V3241U0f5D5wFfQtwPJpbfsX9eqNPJLdav6cxAITK9+vtKHkz8NaygNZOSwFC+LpImzlpIJ5CbmsV6bQ4DoSBobeu4ieclHJI4QflpyzI/lBJxTGCuGhbCqBICRIj9zDMW2p+e3dsdZzCXL97S8DDRgeYOMT3r1OfcBWBdar1hxq6lrWk9TzjZkIKQESVvqqu7fZL2OiSHopLstu9lrTx5CQdK+5+OaHqqmxNv4g7sO5YhqVBmm1c1A98D+sjhwdTjkE0MLyov2GBK1pDLQFGB2hBkuaIfcPn4LzUIMaiwBmdN4+spn11yfhOToMBUQ8G3+tQXSfrPuKY44URHiYGedfUnR9dgv7vmTX7RbivPoQBjFClR5CTq+7ZZ363FE8o/q6BHLsmQyfI3uY+5AhaVcw4SAOLpgku2jQbz6wTdN1SoPlEFgUJI+8rnOkVjpJsYb+3fJeFXBzX242Zw12jIW+pr9Q=='
}

payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "jrnm_get_new_app_deploy_info_using_git",
        "arguments": {}
    },
    "id": 2
}

req = urllib.request.Request(url, method='POST')
for k, v in headers.items():
    req.add_header(k, v)

try:
    with urllib.request.urlopen(req, data=json.dumps(payload).encode()) as response:
        with open("mcp_response.json", "w") as f:
            f.write(response.read().decode())
except Exception as e:
    if hasattr(e, 'read'):
        with open("mcp_response.json", "w") as f:
            f.write(e.read().decode())
    else:
        with open("mcp_response.json", "w") as f:
            f.write(str(e))
