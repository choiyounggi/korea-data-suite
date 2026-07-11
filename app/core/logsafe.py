import re

# data.go.kr puts the API key in the request URL as serviceKey / ServiceKey.
# httpx exception messages embed that full URL, so logging a raw exception leaks
# the key into log files. Redact the value before logging.
#
# Covers the forms a key can appear in if it reaches a log: URL query
# (serviceKey=VALUE), url-encoded (serviceKey%3DVALUE), and JSON / dict-repr
# (\"serviceKey\": \"VALUE\" or 'serviceKey': 'VALUE'). Aliases: service_key, authKey.
_SECRET_RE = re.compile(
    r"(?i)(service_?key|auth_?key)"        # 1: the key name
    r"(['\"]?\s*(?:=|%3d|:)\s*['\"]?)"     # 2: optional closing quote + separator (= / %3D / :) + optional opening quote
    r"([^&\s'\"}]+)"                        # 3: the secret value
)


def redact(text: str) -> str:
    return _SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
