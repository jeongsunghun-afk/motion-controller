

## Tests

```bash
docker build -t mcx-2025-03-37-wheel-builder .
```

```bash
docker run --rm \
  -e USER_ID=$(id -u) \
  -e GROUP_ID=$(id -g) \
  -v $(pwd)/requirements.txt:/app/requirements.txt \
  -v $(pwd)/wheels:/app/wheels \
  mcx-2025-03-37-wheel-builder
```

Remove docker build:
```bash
docker rmi mcx-2025-03-37-wheel-builder
```

Remove all Docker images:
```bash
docker rmi $(docker images -a -q)
```

