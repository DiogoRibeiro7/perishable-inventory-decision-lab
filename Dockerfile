FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3 \
    && poetry config virtualenvs.create false

COPY pyproject.toml README.md ./
COPY src ./src
RUN poetry install --only main --no-interaction --no-ansi

COPY configs ./configs

ENTRYPOINT ["perishable-lab"]
CMD ["demo", "--output-dir", "/tmp/artifacts"]
