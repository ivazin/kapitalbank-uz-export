import dotenv

import kapital


def main():
    keys = dotenv.dotenv_values(".env")

    client = kapital.KapitalAPI(
        pan=keys["PAN"],
        expiry=keys["EXPIRY"],
        app_password=keys["APP_PASSWORD"]
    )

    client.get_all_exports()


if __name__ == '__main__':
    main()
