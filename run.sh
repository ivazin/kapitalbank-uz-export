# подготовка
python3 -m venv venv
source venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt 

# запуск
python3 main.py

# прибраться за собой
deactivate
rm -r venv
rm -r __pycache__

# черновик
# python -m pip freeze > requirements.txt 