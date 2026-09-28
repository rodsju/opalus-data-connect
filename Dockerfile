FROM python:3.11.15-alpine3.24

ENV PYTHONUNBUFFERED=True
ENV PORT=8080

WORKDIR /app

COPY requirements.txt .

# wheel/setuptools so servem para compilar sdist na instalacao (o grpcio nao
# tem wheel musl); saem junto com o pip no fim do mesmo RUN, para nao virarem
# camada. Sem pip, nao da para instalar nada dentro do container em execucao.
RUN python -m pip install --no-cache-dir --upgrade \
        "pip==26.1.2" \
        "wheel==0.46.3" \
        "setuptools==80.10.2" \
    && python -m pip install --no-cache-dir \
        -r requirements.txt \
    && rm -rf \
        /usr/local/lib/python3.11/ensurepip \
        /root/.cache/pip \
    && python -m pip uninstall -y wheel setuptools pip \
    && rm -rf \
        /usr/local/lib/python3.11/site-packages/pip \
        /usr/local/lib/python3.11/site-packages/pip-* \
        /usr/local/lib/python3.11/site-packages/setuptools \
        /usr/local/lib/python3.11/site-packages/setuptools-* \
        /usr/local/lib/python3.11/site-packages/pkg_resources \
        /usr/local/lib/python3.11/site-packages/wheel \
        /usr/local/lib/python3.11/site-packages/wheel-* \
        /usr/local/bin/pip \
        /usr/local/bin/pip3 \
        /usr/local/bin/pip3.11 \
        /usr/local/bin/wheel

COPY . .

# Cloud Run injeta $PORT — forma shell para expandir a variavel
CMD exec python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers
