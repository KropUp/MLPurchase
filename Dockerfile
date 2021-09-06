FROM python:3.9.6

WORKDIR /purchase

RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir pandas sklearn nltk notebook openpyxl pymystem3

CMD ["jupyter", "notebook", "--port=8888", "--no-browser", "--ip=0.0.0.0", "--allow-root"]