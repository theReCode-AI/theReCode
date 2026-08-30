# theReCode Backend

FastAPI backend for the theReCode platform.

## MongoDB

The backend connects to MongoDB on startup and ensures collection indexes are created.

Required environment variables:

- `THERECODE_MONGODB_URI`
- `THERECODE_MONGODB_DATABASE_NAME`

Start local MongoDB:

```bash
docker compose up -d mongodb
```

See the [root README](../README.md) for setup instructions.
