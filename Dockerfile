# Use uma imagem Python oficial como base
FROM python:3.10-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Impede o Python de gerar arquivos .pyc e de bufferizar stdout/stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instala dependências do sistema, se houver (ex: libs para o Pillow)
# Neste caso, não parece haver necessidade, mas é um bom lugar para adicioná-las.
# RUN apt-get update && apt-get install -y ...

# Copia o arquivo de dependências
COPY requirements.txt .

# Instala as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação para o diretório de trabalho
COPY . .

# A aplicação cria/modifica arquivos nos seguintes diretórios.
# É altamente recomendável montar estes diretórios como volumes
# ao executar o contêiner para persistir os dados.
# Exemplo: docker run -v ./data:/app/data -v ./uploads:/app/uploads ...
RUN mkdir -p uploads data static/images

# Expõe a porta que o gunicorn irá escutar
EXPOSE 8000

# Comando para iniciar a aplicação com Gunicorn
# Gunicorn é um servidor WSGI de produção mais robusto que o servidor de desenvolvimento do Flask.
# O Dockerfile não inclui o .env. As variáveis de ambiente (SECRET_KEY, USERNAME, PASSWORD, etc.)
# devem ser injetadas no momento da execução.
# Exemplo: docker run -e SECRET_KEY='seu_segredo_aqui' ...
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
