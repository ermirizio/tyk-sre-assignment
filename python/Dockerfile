FROM python:3.9-slim as base

ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1

FROM base AS python-deps

# Install pipenv and compilation dependencies
RUN pip install pipenv
RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Install python dependencies in /.venv
COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy


FROM base AS runtime

# Copy virtual env from python-deps stage
COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# Create a non-root user and set up working directory
RUN addgroup --system appgroup && adduser --home /home/appuser --system --ingroup appgroup appuser
WORKDIR /app
USER appuser

# Install application into container
COPY . /app

EXPOSE 8004
ENTRYPOINT [ "python", "main.py" ]
CMD ["-k", "~/.kube/kind-config", "--address", "localhost:8004", "--interval", "10"]

