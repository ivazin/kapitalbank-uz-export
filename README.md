# Kapitalbank UZ API data exporter

Простой экспорт достпных по API данных о картах, счетах и транзакциях из Капиталбанка (Узбекистан). Зачем? Увы, ни интернет-банка, ни нормального прилоедние у банка нет )

## Установка

Describe how to install and set up the project, including any installation commands, configuration steps, or dependencies that need to be installed.

```sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt 
```

## Запуск

Нужно заполнить файл .env (см. пример .env-sample) и запустить скрипт:
```sh
python3 main.py 
```
При первом запуске потребуется ввести смс-код. В результате работы в папке программы появится файл с данными Excel.

## Acknowledgments

Спасибо доброму человеку, который как-то где-то раскопал методы:
https://github.com/zenmoney/ZenPlugins/tree/master/src/plugins/kapitalbank-uz
