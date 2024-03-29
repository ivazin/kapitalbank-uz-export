# Проще всего запустить в докере:
docker build -t my-python-app .
docker run -it --rm -v ./:/app my-python-app

#####################################################

# Или в локальном python
python3 -m venv venv.gi
source venv.gi/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt 

# запуск
python3 main.py

# прибраться за собой
deactivate
rm -r venv.gi
rm -r __pycache__

# черновик
# python -m pip freeze > requirements.txt 