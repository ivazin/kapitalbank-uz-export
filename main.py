import asyncio
import datetime
import dotenv
import kapital


async def main():
    keys = dotenv.dotenv_values(".env")

    client = kapital.KapitalAPI(
        pan=keys["PAN"],
        expiry=keys["EXPIRY"],
        app_password=keys["APP_PASSWORD"],
        from_epoch=int(datetime.datetime.strptime("2023-01-01", "%Y-%m-%d").timestamp() * 1000),
        to_epoch=int(datetime.datetime.strptime("2023-10-01", "%Y-%m-%d").timestamp() * 1000)
    )

    await client.get_products_data()
    client.export_to_excel('excel.xlsx')

if __name__ == '__main__':
    asyncio.run(main())
