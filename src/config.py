from oauth2client.service_account import ServiceAccountCredentials

SCOPE = (
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
)

CREDENTIAL = ServiceAccountCredentials.from_json_keyfile_name("creds.json", SCOPE)
