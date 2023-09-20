# Kapitalbank UZ API data exporter

Простой экспорт доступных по API данных о картах, счетах и транзакциях из Капиталбанка (Узбекистан). Зачем? Увы, ни интернет-банка, ни нормального приложения у банка нет )

## Установка

```sh
git clone https://github.com/ivazin/kapitalbank-uz-export.git
cd kapitalbank-uz-export
```
И нужно завести файл `.env` с данными карточки и паролем к приложению (см. пример `.env-sample`).

## Запуск через docker
```
docker build -t my-python-app .
docker run -it --rm -v ./data/:/app/data --env-file .env my-python-app 
```

## Запуск локально
```
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt 
```

```sh
python3 main.py 
```
При первом запуске потребуется ввести смс-код.

В результате работы в папке программы появится файл с данными Excel.

## Acknowledgments

Спасибо доброму человеку, который как-то где-то раскопал методы:
https://github.com/zenmoney/ZenPlugins/tree/master/src/plugins/kapitalbank-uz
