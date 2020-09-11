FROM python
COPY services/aa_backend/requirements.txt /.
RUN pip install -r /requirements.txt
WORKDIR /app
CMD python api.py
