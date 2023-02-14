import kapital, dotenv, pandas as pd

keys = dotenv.dotenv_values(".env")

client = kapital.KapitalAPI(
    pan = keys["PAN"], 
    expiry = keys["EXPIRY"], 
    app_password = keys["APP_PASSWORD"]
)

client.get_all_exports()
