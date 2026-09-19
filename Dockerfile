#Python Version
FROM python:3.14

#Create "app" folder
WORKDIR /app

#Requirement versions
COPY requirements.txt .

#Download all requirement versions from file
RUN pip install --no-cache-dir -r requirements.txt

#Main code pf web-site
COPY main.py .

#Run the web-site
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]