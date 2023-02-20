import datetime
import pickle
import random
import string

import pandas as pd
import requests


class KapitalAPI:
    """
    Класс необходим для получения данных о транзакциях от Капиталбанка (UZ) (Kapitalbank.UZ)

    Аргументы:
        pan (str): номер карты без пробелов и спец. символов
        expiry (str): карта действует до (MMYY)
        app_password (str): пароль, используемый в приложении Капиталбанка
    """

    # список API endpoint-ов
    BASE_URL = "https://online.kapitalbank.uz/api"
    BASE_URL_V2 = f"{BASE_URL}/v2"

    # списки endpoint-ов по счетам и картам
    ENDPOINT_ACCOUNTS_LIST = ["account"]
    ENDPOINT_CARDS_LIST = [
        "uzcard",
        "humo",
        "visa",
        "wallet",
    ]

    KAPITAL_CONFIG_CACHE_FILE = "kapidata.pickle"  #

    from_epoch = datetime.datetime(2021, 1, 1, 0, 0, 0).strftime("%s") + "000"
    to_epoch = datetime.datetime.now().strftime("%s") + "000"

    device_id = ""
    token = ""
    app_name = "TransactionsExporter"
    app_version = "w0.0.2"

    headers_main = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "app-version": app_version,
    }

    cards_ids = []  # здесь будет список пар: (id, тип_карты)
    accounts_ids = []  # здесь будет список id аккаунтов

    def __init__(self, pan, expiry, app_password):
        if len(expiry) != 4 or not expiry.isdigit():
            raise ValueError("Expiry must be 4 numbers (characters): 0124 (MMYY)")
        if not pan.isdigit():
            raise ValueError("Pan should be numeric: 1111222...4444 (Card number)")
        self.pan = pan
        self.expiry = expiry
        self.app_password = app_password
        if not self._load():
            self.first_run()

    def _gen_device(self, length=32, chars=None):
        if not chars:
            chars = string.ascii_letters + string.digits  # + string.punctuation
        return "".join(random.choice(chars) for _ in range(length))

    def _save(self):
        with open(self.KAPITAL_CONFIG_CACHE_FILE, "wb") as handle:
            pickle.dump(
                {
                    "device_id": self.device_id,
                    "token": self.token,
                    "phone": self.phone,
                },
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    def _load(self):
        try:
            with open(self.KAPITAL_CONFIG_CACHE_FILE, "rb") as handle:
                data_loaded = pickle.load(handle)
        except Exception as e:
            print("Ошибка при обновлении токена:", e)
            return False
        else:
            self.token = data_loaded.get("token")
            self.device_id = data_loaded.get("device_id")
            self.phone = data_loaded.get("phone")
            if self.token != "":
                return True
            else:
                return False

    def device_reg(self):
        endpoint = f"{self.BASE_URL}/device"
        self.device_id = self._gen_device(32)
        payload = f'{{ "deviceId" : "{self.device_id}", "name" : "{self.app_name}" }}'
        headers = {**self.headers_main}
        response = requests.request("POST", endpoint, headers=headers, data=payload)
        result_json = response.json()
        assert result_json.get("data", {}).get("message", {}) == "Success"

    def check_user(self):
        endpoint = f"{self.BASE_URL}/check-client-card"
        payload = f'{{"pan": "{self.pan}", "expiry": "{self.expiry}"}}'
        headers = {**self.headers_main, "device-id": self.device_id}
        response = requests.request("POST", endpoint, headers=headers, data=payload)
        result_json = response.json()
        self.phone = result_json.get("data", {}).get("phone", "")
        assert self.phone != ""

    def send_sms(self):
        endpoint = f"{self.BASE_URL_V2}/login"
        payload = f'{{ "pan": "{self.pan}", "expiry": "{self.expiry}", "password": "{self.app_password}", "reserveSms": "false"}}'
        headers = {**self.headers_main, "device-id": self.device_id}
        response = requests.request("POST", endpoint, headers=headers, data=payload)
        result_json = response.json()
        error = result_json.get("errorMessage", "")
        assert error == ""

    def input_sms_code(self):
        self.sms_code = input("Введите код из смски: ")
        print("Ввели:", self.sms_code)

    def get_token(self):
        endpoint = f"{self.BASE_URL}/registration/verify/{self.sms_code}/{self.phone}"
        headers = {**self.headers_main, "device-id": self.device_id}
        response = requests.request("POST", endpoint, headers=headers, data="{}")
        result_json = response.json()
        error = result_json.get("errorMessage", "")
        assert error == ""
        self.fcm_token = result_json.get("data", {}).get("fcm_token", "")
        self.token = result_json.get("data", {}).get("token", "")
        assert self.token != ""

    def first_run(self):
        self.device_reg()
        self.updateToken()

    def updateToken(self):
        try:
            self.check_user()
            self.send_sms()
            self.input_sms_code()
            self.get_token()
            self._save()
        except Exception as e:
            print("Ошибка при обновлении токена:", e)

    def get_cards_df(self):
        df = pd.DataFrame()
        self.cards_ids = []
        headers = {
            **self.headers_main,
            "device-id": self.device_id,
            "token": self.token,
        }
        for c in self.ENDPOINT_CARDS_LIST:
            response = requests.request(
                "GET", f"{self.BASE_URL}/{c}", headers=headers, data={}
            )
            if response.json().get("errorMessage", "") == "Invalid Token":
                self.updateToken()
                headers["token"] = self.token
                response = requests.request(
                    "GET", f"{self.BASE_URL}/{c}", headers=headers, data={}
                )

            new_df = pd.json_normalize(response.json().get("data", {}))
            if not new_df.empty:
                new_df["card"] = c
                df = pd.concat([df, new_df])
                self.cards_ids.extend([(id, c) for id in new_df["id"].tolist()])

        return df

    def get_accounts_df(self):
        df = pd.DataFrame()
        headers = {
            **self.headers_main,
            "device-id": self.device_id,
            "token": self.token,
        }
        for c in self.ENDPOINT_ACCOUNTS_LIST:
            response = requests.request(
                "GET", f"{self.BASE_URL}/{c}", headers=headers, data={}
            )
            if response.json().get("errorMessage", "") == "Invalid Token":
                self.updateToken()
                headers["token"] = self.token
                response = requests.request(
                    "GET", f"{self.BASE_URL}/{c}", headers=headers, data={}
                )

            new_df = pd.json_normalize(response.json().get("data", {}))
            if not new_df.empty:
                df = pd.concat([df, new_df])
        self.accounts_ids = df["id"].tolist()
        return df

    def get_uzcard_history_df(self):
        df = pd.DataFrame()
        if len(self.cards_ids) == 0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "uzcard":
                endpoint = f"{self.BASE_URL}/{card}/history?cardId={id}&dateFrom={self.from_epoch}&dateTo={self.to_epoch}"

                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})

                d = response.json().get("data", [])
                if len(d) != 0 and isinstance(d, dict):
                    new_df = pd.json_normalize(
                        response.json().get("data", {}).get("data", {})
                    )
                    if not new_df.empty:
                        new_df["card_id"] = id
                        df = pd.concat([df, new_df])

        df["utime_datetime"] = pd.to_datetime(df["utime"], unit="ms")
        df["udate_datetime"] = pd.to_datetime(df["udate"], unit="ms")

        return df

    def get_visa_history_df(self):
        df = pd.DataFrame()
        if len(self.cards_ids) == 0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "visa":
                endpoint = f"{self.BASE_URL}/{card}/history?cardId={id}&dateFrom={self.from_epoch}&dateTo={self.to_epoch}"

                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})
                d = response.json().get("data", [])
                if len(d) != 0 and isinstance(d, list):
                    new_df = pd.json_normalize(response.json().get("data", {}))
                    if not new_df.empty:
                        new_df["card_id"] = id
                        df = pd.concat([df, new_df])
        if not df.empty:
            df["transDate_datetime"] = pd.to_datetime(df["transDate"], unit="ms")

        return df

    def get_humo_history_df(self):
        df = pd.DataFrame()
        if len(self.cards_ids) == 0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "humo":
                endpoint = f"{self.BASE_URL}/{card}/history?cardId={id}&dateFrom={self.from_epoch}&dateTo={self.to_epoch}"

                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})

                d = response.json().get("data", [])

                if len(d) != 0 and isinstance(d, list):
                    new_df = pd.json_normalize(response.json().get("data", {}))
                    if not new_df.empty:
                        new_df["card_id"] = id
                        df = pd.concat([df, new_df])

        return df

    def get_wallet_history_df(self):
        df = pd.DataFrame()
        if len(self.cards_ids) == 0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "wallet":
                endpoint = f"{self.BASE_URL}/{card}/history?id={id}&startDate={self.from_epoch}&endDate={self.to_epoch}"

                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})

                d = response.json().get("data", [])

                if len(d) != 0 and isinstance(d, list):
                    new_df = pd.json_normalize(response.json().get("data", {}))
                    if not new_df.empty:
                        new_df["card_id"] = id
                        df = pd.concat([df, new_df])

        return df

    def get_accounts_history_df(self):
        df = pd.DataFrame()
        if len(self.accounts_ids) == 0:
            self.get_accounts_df()
        for id in self.accounts_ids:
            endpoint = f"{self.BASE_URL}/account/statement?id={id}&startDate={self.from_epoch}&endDate={self.to_epoch}"
            headers = {
                **self.headers_main,
                "device-id": self.device_id,
                "token": self.token,
            }
            response = requests.request("GET", endpoint, headers=headers, data={})
            d = response.json().get("data", [])
            if len(d) != 0 and isinstance(d, list):
                new_df = pd.json_normalize(
                    response.json().get("data", {}).get("data", {})
                )
                if not new_df.empty:
                    new_df["card_id"] = id
                    df = pd.concat([df, new_df])
        return df

    # Главный метод, который наносит основную пользу
    def get_all_exports(self, fname="export_ALL.xlsx"):

        df_c = self.get_cards_df()
        df_ac = self.get_accounts_df()
        t1 = self.get_uzcard_history_df()
        t2 = self.get_visa_history_df()
        t3 = self.get_wallet_history_df()
        t4 = self.get_humo_history_df()
        t5 = self.get_accounts_history_df()

        with pd.ExcelWriter(fname, engine="xlsxwriter") as writer:
            df_c.to_excel(writer, sheet_name="cards", index=False)
            df_ac.to_excel(writer, sheet_name="accounts", index=False)
            t1.to_excel(writer, sheet_name="card-uzcard transactions", index=False)
            t2.to_excel(writer, sheet_name="card-visa transactions", index=False)
            t3.to_excel(writer, sheet_name="card-wallet transactions", index=False)
            t4.to_excel(writer, sheet_name="card-humo transactions", index=False)
            t5.to_excel(writer, sheet_name="accounts transactions", index=False)

            for sht_name in writer.sheets:
                ws = writer.sheets[sht_name]
                ws.freeze_panes(1, 0)
