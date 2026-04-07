from fyers_apiv3 import fyersModel
from fyers_apiv3 import accessToken

client_id = "YOUR_CLIENT_ID"
secret_key = "YOUR_SECRET_KEY"
redirect_uri = "http://127.0.0.1:8000/"

session = accessToken.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type="code",
    grant_type="authorization_code"
)

# Step 1: Get login URL
print(session.generate_authcode())