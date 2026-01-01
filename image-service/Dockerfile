FROM osgeo/gdal:ubuntu-small-3.6.2

RUN apt-get update && apt-get install -y python3-pip

WORKDIR /app

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]