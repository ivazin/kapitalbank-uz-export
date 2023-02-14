import requests, json, datetime, time, pickle, random, string
import pandas as pd


class KapitalAPI:
    base_url = "https://online.kapitalbank.uz/api"
    base_url_v2 = "https://online.kapitalbank.uz/api/v2"

    endpoint_cards_list = ["uzcard", "humo", "visa", "wallet"]
    endpoint_accounts_list = ["account"]

    from_epoch = datetime.datetime(2022, 1, 1, 0, 0, 0).strftime("%s") + "000"
    to_epoch = datetime.datetime.now().strftime("%s") + "000"

    device_id = ""
    token = ""

    app_name = "TransactionsExporter"
    app_version = "w0.0.2"

    kapital_config_file = "kapidata.pickle"

    headers_main = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "app-version": app_version,
    }

    # is_loaded = False
    cards_ids = []  # здесь будет список пар: (id, тип_карты)
    accounts_ids = []  # здесь будет список id аккаунтов

    def __init__(self, pan, expiry, app_password):
        if len(expiry) != 4 or not expiry.isdigit():
            raise ValueError(f"Expiry must be 4 numbers (characters): 0124 (MMYY)")
        if not pan.isdigit():
            raise ValueError(f"Pan should be numeric: 1111222...4444 (Card number)")
        self.pan = pan
        self.expiry = expiry
        self.app_password = app_password
        if not self._load():
            # print("NOT LOADED")
            self.first_run()

    def _gen_device(self, length=32, chars=None):
        if not chars:
            chars = string.ascii_letters + string.digits  # + string.punctuation
        return "".join(random.choice(chars) for _ in range(length))

    def _save(self):
        with open(self.kapital_config_file, "wb") as handle:
            pickle.dump(
                {
                    "device_id": self.device_id,
                    # 'app_name': self.app_name,
                    "token": self.token,
                    "phone": self.phone,
                },
                handle,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    def _load(self):
        try:
            with open(self.kapital_config_file, "rb") as handle:
                data_loaded = pickle.load(handle)
                # print("Loaded!")
        except Exception as e:
            # есил нет кэша, скачаем и сохраним его
            # print(e)
            # self.is_loaded = False
            return False
        else:
            self.token = data_loaded.get("token")
            self.device_id = data_loaded.get("device_id")
            # self.app_name = data_loaded.get('app_name')
            self.phone = data_loaded.get("phone")
            # print("Load:", self.token, self.device_id, self.phone)
            if self.token != "":
                # self.is_loaded = True
                return True
            else:
                return False

    def device_reg(self):
        endpoint = f"{self.base_url}/device"
        self.device_id = self._gen_device(32)
        payload = f'{{ "deviceId" : "{self.device_id}", "name" : "{self.app_name}" }}'
        headers = {**self.headers_main}
        response = requests.request("POST", endpoint, headers=headers, data=payload)
        result_json = response.json()
        # print(result_json)
        assert result_json.get("data", {}).get("message", {}) == "Success"

    def check_user(self):
        endpoint = f"{self.base_url}/check-client-card"
        payload = f'{{"pan": "{self.pan}", "expiry": "{self.expiry}"}}'
        headers = {**self.headers_main, "device-id": self.device_id}
        response = requests.request("POST", endpoint, headers=headers, data=payload)
        # print(response.text)
        result_json = response.json()
        # print(result_json)
        self.phone = result_json.get("data", {}).get("phone", "")
        assert self.phone != ""
        # print('Записали телефон:', self.phone)

    def send_sms(self):
        endpoint = f"{self.base_url_v2}/login"
        payload = f'{{ "pan": "{self.pan}", "expiry": "{self.expiry}", "password": "{self.app_password}", "reserveSms": "false"}}'
        headers = {**self.headers_main, "device-id": self.device_id}
        response = requests.request("POST", endpoint, headers=headers, data=payload)
        # print(response.text)
        result_json = response.json()
        # print(result_json)
        error = result_json.get("errorMessage", "")
        assert error == ""
        # {"data":{"message":"**** 0837"},"errorMessage":"","timestamp":1676245305489}

    def input_sms_code(self):
        self.sms_code = input("Введите код из смски: ")
        print("Ввели:", self.sms_code)

    def get_token(self):
        endpoint = f"{self.base_url}/registration/verify/{self.sms_code}/{self.phone}"
        headers = {**self.headers_main, "device-id": self.device_id}
        response = requests.request("POST", endpoint, headers=headers, data="{}")
        # print(response.text)
        result_json = response.json()
        # print(result_json)
        error = result_json.get("errorMessage", "")
        assert error == ""
        self.fcm_token = result_json.get("data", {}).get("fcm_token", "")
        self.token = result_json.get("data", {}).get("token", "")
        assert self.token != ""

    def first_run(self):
        self.device_reg()
        self.updateToken()

    def updateToken(self):
        self.check_user()
        self.send_sms()
        self.input_sms_code()
        self.get_token()
        self._save()

    # def get_accounts(self):
    #     endpoint_cards_list = ['uzcard', 'humo', 'visa', 'wallet']
    #     endpoint_accounts_list = ['account']

    #     headers = {**self.headers_main, 'device-id': self.device_id, 'token': self.token}

    #     res_data = []
    #     for endpoint in endpoint_cards_list:
    #         response = requests.request("GET", f'{self.base_url}/{endpoint}', headers=headers, data={})
    #         result_json = response.json()

    #         print(response.text)
    #         print(json.dumps(result_json, indent=4))
    #         res_data.append(result_json.get("data", {}))

    def get_cards_df(self):
        df = pd.DataFrame()
        self.cards_ids = []
        headers = {
            **self.headers_main,
            "device-id": self.device_id,
            "token": self.token,
        }
        for c in self.endpoint_cards_list:
            response = requests.request(
                "GET", f"{self.base_url}/{c}", headers=headers, data={}
            )
            if response.json().get("errorMessage", "") == "Invalid Token":
                self.updateToken()
                headers["token"] = self.token
                response = requests.request(
                    "GET", f"{self.base_url}/{c}", headers=headers, data={}
                )
            # return response.json().get("data", {})
            # print(f"CARDS!!! {c}")
            # print(json.dumps(response.json(), indent=4))
            new_df = pd.json_normalize(response.json().get("data", {}))
            if not new_df.empty:
                new_df["card"] = c
                df = pd.concat([df, new_df])
                self.cards_ids.extend([(id, c) for id in new_df["id"].tolist()])
            # print("List:", self.cards_ids)
        # print(self.cards_ids)
        return df

    def get_accounts_df(self):
        df = pd.DataFrame()
        headers = {
            **self.headers_main,
            "device-id": self.device_id,
            "token": self.token,
        }
        for c in self.endpoint_accounts_list:
            response = requests.request(
                "GET", f"{self.base_url}/{c}", headers=headers, data={}
            )
            if response.json().get("errorMessage", "") == "Invalid Token":
                self.updateToken()
                headers["token"] = self.token
                response = requests.request(
                    "GET", f"{self.base_url}/{c}", headers=headers, data={}
                )

            # return response.json().get("data", {})
            new_df = pd.json_normalize(response.json().get("data", {}))
            if not new_df.empty:
                df = pd.concat([df, new_df])
        self.accounts_ids = df["id"].tolist()
        return df

    def get_uzcard_history_df(self):
        df = pd.DataFrame()
        if len(self.cards_ids)==0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "uzcard":
                endpoint = f"{self.base_url}/{card}/history?cardId={id}&dateFrom={self.from_epoch}&dateTo={self.to_epoch}"
                # print("!!!", endpoint)
                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})
                # print(json.dumps(response.json(), indent=4))

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
        if len(self.cards_ids)==0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "visa":
                endpoint = f"{self.base_url}/{card}/history?cardId={id}&dateFrom={self.from_epoch}&dateTo={self.to_epoch}"
                # print("!!!", endpoint)
                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})
                # print(json.dumps(response.json(), indent=4))

                d = response.json().get("data", [])
                # print(d)
                if len(d) != 0 and isinstance(d, list):
                    new_df = pd.json_normalize(response.json().get("data", {}))
                    if not new_df.empty:
                        new_df["card_id"] = id
                        df = pd.concat([df, new_df])
        if not df.empty:
            df["transDate_datetime"] = pd.to_datetime(df["transDate"], unit="ms")
        # df['udate_datetime'] = pd.to_datetime(df['udate'], unit='ms')

        return df

    def get_humo_history_df(self):
        df = pd.DataFrame()
        if len(self.cards_ids)==0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "humo":
                endpoint = f"{self.base_url}/{card}/history?cardId={id}&dateFrom={self.from_epoch}&dateTo={self.to_epoch}"
                # print("!!!", endpoint)
                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})
                # print(json.dumps(response.json(), indent=4))

                d = response.json().get("data", [])
                # print(d)
                if len(d) != 0 and isinstance(d, list):
                    new_df = pd.json_normalize(response.json().get("data", {}))
                    if not new_df.empty:
                        new_df["card_id"] = id
                        df = pd.concat([df, new_df])
        # if not df.empty:
        #     df['transDate_datetime'] = pd.to_datetime(df['transDate'], unit='ms')

        return df

    def get_wallet_history_df(self):
        df = pd.DataFrame()
        if len(self.cards_ids)==0:
            self.get_cards_df()
        for id, card in self.cards_ids:
            if card == "wallet":
                endpoint = f"{self.base_url}/{card}/history?id={id}&startDate={self.from_epoch}&endDate={self.to_epoch}"
                # print("!!!", endpoint)
                headers = {
                    **self.headers_main,
                    "device-id": self.device_id,
                    "token": self.token,
                }
                response = requests.request("GET", endpoint, headers=headers, data={})
                # print(json.dumps(response.json(), indent=4))

                d = response.json().get("data", [])
                # print(d)
                if len(d) != 0 and isinstance(d, list):
                    new_df = pd.json_normalize(response.json().get("data", {}))
                    if not new_df.empty:
                        new_df["card_id"] = id
                        df = pd.concat([df, new_df])
        # if not df.empty:
        #     df['transDate_datetime'] = pd.to_datetime(df['transDate'], unit='ms')
        # df['udate_datetime'] = pd.to_datetime(df['udate'], unit='ms')

        return df

    def get_accounts_history_df(self):
        df = pd.DataFrame()
        if len(self.accounts_ids)==0:
            self.get_accounts_df()
        for id in self.accounts_ids:
            endpoint = f"{self.base_url}/account/statement?id={id}&startDate={self.from_epoch}&endDate={self.to_epoch}"
            headers = {
                **self.headers_main,
                "device-id": self.device_id,
                "token": self.token,
            }
            response = requests.request("GET", endpoint, headers=headers, data={})
            d = response.json().get("data", [])
            # print(d)
            if len(d) != 0 and isinstance(d, list):
                new_df = pd.json_normalize(
                    response.json().get("data", {}).get("data", {})
                )
                if not new_df.empty:
                    new_df["card_id"] = id
                    df = pd.concat([df, new_df])
        return df


    def get_all_exports(self, fname = 'export_ALL.xlsx'):
        
        df_c = self.get_cards_df()
        df_ac = self.get_accounts_df()
        t1 = self.get_uzcard_history_df()
        t2 = self.get_visa_history_df()
        t3 = self.get_wallet_history_df()
        t4 = self.get_humo_history_df()
        t5 = self.get_accounts_history_df()

        # df_c.to_excel('export_cards_data.xlsx', index=False)
        # df_ac.to_excel('export_accounts_data.xlsx', index=False)
        # t1.to_excel('export_get_uzcard_history_df.xlsx', index=False)
        # t2.to_excel('export_get_visa_history_df.xlsx', index=False)
        # t3.to_excel('export_get_wallet_history_df.xlsx', index=False)
        # t4.to_excel('export_get_humo_history_df.xlsx', index=False)
        # t5.to_excel('export_get_accounts_history_df.xlsx', index=False)
        # tmp = pd.concat([t1, t2])
        # tmp.to_excel('export_all_uzcard+visa_transactions.xlsx', index=False)

        with pd.ExcelWriter(fname, engine='xlsxwriter') as writer:
            df_c.to_excel(writer, sheet_name='cards', index=False)
            df_ac.to_excel(writer, sheet_name='accounts', index=False)
            t1.to_excel(writer, sheet_name='card-uzcard transactions', index=False)
            t2.to_excel(writer, sheet_name='card-visa transactions', index=False)
            t3.to_excel(writer, sheet_name='card-wallet transactions', index=False)
            t4.to_excel(writer, sheet_name='card-humo transactions', index=False)
            t5.to_excel(writer, sheet_name='accounts transactions', index=False)

            # # get the workbook object to access its sheets
            # workbook = writer.book
            # # iterate over each sheet and freeze the first row
            # for sheet in workbook.worksheets():
            #     sheet.freeze_panes(1, 0)

            for sht_name in writer.sheets:
                ws = writer.sheets[sht_name]
                ws.freeze_panes(1,0)

            # writer.save()