import asyncio
import datetime
import pickle
import random
import string

import aiohttp
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

    # файл для хранения токена, чтобы постоянно не вводить смски и не вызывать вопросов у банка
    KAPITAL_CONFIG_CACHE_FILE = "kapidata.pickle"

    # даты С и ДО какого момента запрашивать транзации
    from_epoch = datetime.datetime(2023, 1, 1, 0, 0, 0).strftime("%s") + "000"
    to_epoch = datetime.datetime.now().strftime("%s") + "000"
    days_chunk=30

    device_id = ""
    token = ""
    app_name = "TransactionsExporter"
    app_version = "w0.0.2"

    headers_main = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "app-version": app_version,
    }

    def __init__(self, pan, expiry, app_password, from_epoch = None, to_epoch = None):
        if len(expiry) != 4 or not expiry.isdigit():
            raise ValueError("Expiry must be 4 numbers (characters): 0124 (MMYY)")
        if not pan.isdigit():
            raise ValueError("Pan should be numeric: 1111222...4444 (Card number)")
        self.pan = pan
        self.expiry = expiry
        self.app_password = app_password
        if not self._load():
            self.first_run()
        if from_epoch:
            self.from_epoch = from_epoch
        if to_epoch:
            self.to_epoch = to_epoch

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

    def _splits(self, from_epoch, to_epoch, segment_length=datetime.timedelta(days=21)):

        from_date = datetime.datetime.fromtimestamp(float(from_epoch)/1000.0)
        to_date = datetime.datetime.fromtimestamp(float(to_epoch)/1000.0)

        segment_start = from_date
        segment_end = from_date + segment_length

        while segment_end <= to_date:
            yield(int(segment_start.timestamp()*1000), int(segment_end.timestamp()*1000))

            segment_start = segment_end
            segment_end = segment_end + segment_length

        if segment_start < to_date:
            yield(int(segment_start.timestamp()*1000), int(to_date.timestamp()*1000))

    def device_reg(self):
        try:
            endpoint = f"{self.BASE_URL}/device"
            self.device_id = self._gen_device(32)
            payload = f'{{ "deviceId" : "{self.device_id}", "name" : "{self.app_name}" }}'
            headers = {**self.headers_main}
            response = requests.request("POST", endpoint, headers=headers, data=payload)
            result_json = response.json()
            assert result_json.get("data", {}).get("message", {}) == "Success"
        except Exception as e:
            print("Ошибка при регистрации девайса:", e)

    def check_user(self):
        try:
            endpoint = f"{self.BASE_URL}/check-client-card"
            payload = f'{{"pan": "{self.pan}", "expiry": "{self.expiry}"}}'
            headers = {**self.headers_main, "device-id": self.device_id}
            response = requests.request("POST", endpoint, headers=headers, data=payload)
            result_json = response.json()
            self.phone = result_json.get("data", {}).get("phone", "")
            assert self.phone != ""
        except Exception as e:
            print("Ошибка при проверки пользовательской карты:", e)

    def send_sms(self):
        try:
            endpoint = f"{self.BASE_URL_V2}/login"
            payload = f'{{ "pan": "{self.pan}", "expiry": "{self.expiry}", "password": "{self.app_password}", "reserveSms": "false"}}'
            headers = {**self.headers_main, "device-id": self.device_id}
            response = requests.request("POST", endpoint, headers=headers, data=payload)
            result_json = response.json()
            error = result_json.get("errorMessage", "")
            assert error == ""
        except Exception as e:
            print("Ошибка при отправке смс:", e)

    def input_sms_code(self):
        self.sms_code = input("Введите код из смски: ")

    def get_token(self):
        try:
            endpoint = f"{self.BASE_URL}/registration/verify/{self.sms_code}/{self.phone}"
            headers = {**self.headers_main, "device-id": self.device_id}
            response = requests.request("POST", endpoint, headers=headers, data="{}")
            result_json = response.json()
            error = result_json.get("errorMessage", "")
            assert error == ""
            self.fcm_token = result_json.get("data", {}).get("fcm_token", "")
            self.token = result_json.get("data", {}).get("token", "")
            assert self.token != ""
        except Exception as e:
            print("Ошибка при получении токена:", e)

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

    async def fetch_data(self, session, endpoint, params=None):
        headers = {
            **self.headers_main,
            "device-id": self.device_id,
            "token": self.token,
        }
        async with session.get(f"{self.BASE_URL}/{endpoint}", headers=headers, data={}, params=params) as response:
            print(f"Gettind data from {self.BASE_URL}/{endpoint}", params)
            if response.status == 200:
                data = await response.json()
                return data
            else:
                return None

    async def get_visa_cards_transactions(self, session, from_date=None, to_date=None):
        tasks = []
        for r in self.response_visa.get("data", {}):
            for a, b in self._splits(from_date, to_date, datetime.timedelta(days=self.days_chunk)):
                tasks.append(self.fetch_data(session, 'visa/history', params={'cardId': r['id'], 'dateFrom': a, 'dateTo': b}))
        responses = await asyncio.gather(*tasks)
        df = pd.DataFrame()
        for response in responses:
            data = response.get('data', [])
            if data:
                new_df = pd.json_normalize(data)
                df = pd.concat([df, new_df], ignore_index=True)
        if not df.empty:
            df = df.sort_values(by='transDate', ascending=False)
            df["transDate_datetime"] = pd.to_datetime(df["transDate"], unit="ms")
        return df

    async def get_uzcard_cards_transactions(self, session, from_date=None, to_date=None):
        tasks = []
        for r in self.response_uzcard.get("data", {}):
            for a, b in self._splits(from_date, to_date, datetime.timedelta(days=self.days_chunk)):
                tasks.append(self.fetch_data(session, 'uzcard/history', params={'cardId': r['id'], 'dateFrom': a, 'dateTo': b}))
        responses = await asyncio.gather(*tasks)
        df = pd.DataFrame()
        for response in responses:
            data = response.get('data', {})
            if data:
                new_df = pd.json_normalize(data.get('data',[]))
                df = pd.concat([df, new_df], ignore_index=True)
        if not df.empty:
            df = df.sort_values(by='utime', ascending=False)
            df["utime_datetime"] = pd.to_datetime(df["utime"], unit="ms")
            df["udate_datetime"] = pd.to_datetime(df["udate"], unit="ms")
        return df

    async def get_humo_cards_transactions(self, session, from_date=None, to_date=None):
        tasks = []
        for r in self.response_humo.get("data", {}):
            for a, b in self._splits(from_date, to_date, datetime.timedelta(days=self.days_chunk)):
                tasks.append(self.fetch_data(session, 'humo/history', params={'cardId': r['id'], 'dateFrom': a, 'dateTo': b}))
        responses = await asyncio.gather(*tasks)
        df = pd.DataFrame()
        for response in responses:
            data = response.get('data', {})
            if data:
                new_df = pd.json_normalize(data)
                df = pd.concat([df, new_df], ignore_index=True)
        return df

    async def get_wallets_transactions(self, session, from_date=None, to_date=None):
        tasks = []
        for r in self.response_wallet.get("data", {}):
            for a, b in self._splits(from_date, to_date, datetime.timedelta(days=self.days_chunk)):
                tasks.append(self.fetch_data(session, 'wallet/history', params={'id': r['id'], 'startDate': a, 'endDate': b}))
        responses = await asyncio.gather(*tasks)
        df = pd.DataFrame()
        for response in responses:
            data = response.get('data', {})
            if data:
                new_df = pd.json_normalize(data)
                df = pd.concat([df, new_df], ignore_index=True)
        if not df.empty:
            df = df.sort_values(by='date', ascending=False)
            df["date_datetime"] = pd.to_datetime(df["date"], unit="ms")
            df["amount"] = df["amount"] / 100
        return df


    async def get_accounts_transactions(self, session, from_date=None, to_date=None):
        tasks = []
        for r in self.response_account.get("data", {}):
            for a, b in self._splits(from_date, to_date, datetime.timedelta(days=self.days_chunk)):
                tasks.append(self.fetch_data(session, 'account/statement', params={'id': r['id'], 'startDate': a, 'endDate': b}))
        responses = await asyncio.gather(*tasks)
        df = pd.DataFrame()
        for response in responses:
            data = response.get('data', {})
            if data:
                new_df = pd.json_normalize(data)
                df = pd.concat([df, new_df], ignore_index=True)
        if not df.empty:
            df = df.sort_values(by='date', ascending=False)
            df["date_datetime"] = pd.to_datetime(df["date"], unit="ms")
            df["dateTransact_datetime"] = pd.to_datetime(df["dateTransact"], unit="ms")
            df["amount"] = df["amount"] / 100
        return df

    async def get_deposits_transactions(self, session, from_date=None, to_date=None):
        tasks = []
        for r in self.response_deposit.get("data", {}):
            for a, b in self._splits(from_date, to_date, datetime.timedelta(days=self.days_chunk)):
                tasks.append(self.fetch_data(session, 'deposit/statement', params={'absId': r['absId'], 'startDate': a, 'endDate': b}))
        responses = await asyncio.gather(*tasks)
        df = pd.DataFrame()
        for response in responses:
            data = response.get('data', {})
            if data:
                new_df = pd.json_normalize(data)
                df = pd.concat([df, new_df], ignore_index=True)
        # df = df.sort_values(by='docId', ascending=False)
        if not df.empty:
            df = df.sort_values(by='valueDate', ascending=False)
            df["bookingDate_datetime"] = pd.to_datetime(df["bookingDate"], unit="ms")
            df["docDate_datetime"] = pd.to_datetime(df["docDate"], unit="ms")
            df["valueDate_datetime"] = pd.to_datetime(df["valueDate"], unit="ms")
            df["amount"] = df["amount"] / 100
        return df
       
    async def get_products_data(self, from_date=from_epoch, to_date=to_epoch):
        self.cards = {}
        tasks = []
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.fetch_data(session, 'account'),
                self.fetch_data(session, 'deposit'),
                self.fetch_data(session, 'uzcard'),
                self.fetch_data(session, 'humo'),
                self.fetch_data(session, 'visa'),
                self.fetch_data(session, 'wallet'),
            ]

            responses = await asyncio.gather(*tasks)

            self.response_account, \
            self.response_deposit, \
            self.response_uzcard, \
            self.response_humo, \
            self.response_visa, \
            self.response_wallet = responses

            self.account_df = pd.json_normalize(self.response_account.get("data", {}))
            self.deposit_df = pd.json_normalize(self.response_deposit.get("data", {}))
            self.uzcard_df = pd.json_normalize(self.response_uzcard.get("data", {}))
            self.humo_df = pd.json_normalize(self.response_humo.get("data", {}))
            self.visa_df = pd.json_normalize(self.response_visa.get("data", {}))
            self.wallet_df = pd.json_normalize(self.response_wallet.get("data", {}))

            self.visa_tx_df = await self.get_visa_cards_transactions(session, from_date=from_date, to_date=to_date)
            self.uzcard_tx_df = await self.get_uzcard_cards_transactions(session, from_date=from_date, to_date=to_date)
            self.humo_tx_df = await self.get_humo_cards_transactions(session, from_date=from_date, to_date=to_date)
            self.wallet_tx_df = await self.get_wallets_transactions(session, from_date=from_date, to_date=to_date)
            self.account_tx_df = await self.get_accounts_transactions(session, from_date=from_date, to_date=to_date)
            self.deposit_tx_df = await self.get_deposits_transactions(session, from_date=from_date, to_date=to_date)

    def export_to_excel(self, fname = 'excel.xlsx'):
        with pd.ExcelWriter(fname, engine="xlsxwriter") as writer:

            self.visa_df.to_excel(writer, sheet_name="visa", index=False)
            self.visa_tx_df.to_excel(writer, sheet_name="visa_tx", index=False)

            self.uzcard_df.to_excel(writer, sheet_name="uzcard", index=False)
            self.uzcard_tx_df.to_excel(writer, sheet_name="uzcard_tx", index=False)

            self.humo_df.to_excel(writer, sheet_name="humo", index=False)
            self.humo_tx_df.to_excel(writer, sheet_name="humo_tx", index=False)

            self.wallet_df.to_excel(writer, sheet_name="wallet", index=False)
            self.wallet_tx_df.to_excel(writer, sheet_name="wallets_tx", index=False)

            self.account_df.to_excel(writer, sheet_name="account", index=False)
            self.account_tx_df.to_excel(writer, sheet_name="accounts_tx", index=False)

            self.deposit_df.to_excel(writer, sheet_name="deposit", index=False)
            self.deposit_tx_df.to_excel(writer, sheet_name="deposits_tx", index=False)
            for sht_name in writer.sheets:
                ws = writer.sheets[sht_name]
                ws.freeze_panes(1, 0)

        print("EXPORTED:", fname)