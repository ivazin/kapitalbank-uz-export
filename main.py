import dotenv

import kapital


def main():
    keys = dotenv.dotenv_values(".env")

    client = kapital.KapitalAPI(
        pan=keys["PAN"],
        expiry=keys["EXPIRY"],
        app_password=keys["APP_PASSWORD"]
    )

    df_c = client.get_cards_df()
    df_ac = client.get_accounts_df()
    # t1 = client.get_uzcard_history_df()
    # t2 = client.get_visa_history_df()
    # t3 = client.get_wallet_history_df()
    # t4 = client.get_humo_history_df()
    t2 = client.get_all_cards_history_df()

    client.save_all_cards_history_df()
    


if __name__ == '__main__':
    main()
