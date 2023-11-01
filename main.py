import asyncio
import datetime
import dotenv
import kapital
import os


async def main():
    # keys = dotenv.dotenv_values(".env")
    keys = {
        **dotenv.dotenv_values(".env"),
        **os.environ,
    }

    client = kapital.KapitalAPI(
        pan=keys["PAN"],
        expiry=keys["EXPIRY"],
        app_password=keys["APP_PASSWORD"],
        from_epoch=int(datetime.datetime.strptime("2023-01-01", "%Y-%m-%d").timestamp() * 1000),
        to_epoch=int(datetime.datetime.strptime("2024-01-01", "%Y-%m-%d").timestamp() * 1000),
        data_path=keys["DATA_DIR"]
    )

    await client.get_products_data()
    client.export_to_excel('excel.xlsx')

if __name__ == '__main__':
    asyncio.run(main())
