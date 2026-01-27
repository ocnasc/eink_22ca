# API Routes

This document describes the available API routes for the e-ink display project.

## Authentication

All API endpoints require Bearer Token authentication. The token must be provided in the `Authorization` header.

```
Authorization: Bearer <YOUR_TOKEN>
```

---

## 1. Check for Available Image

This endpoint allows you to check if a new image is available and get its metadata.

- **URL:** `/api/image/available`
- **Method:** `GET`
- **Authentication:** Bearer Token

### Example Request (curl)

Replace `<YOUR_TOKEN>` with your actual Bearer token.

```bash
curl -X GET http://eink.mandates.chat/api/image/available \
  -H "Authorization: Bearer b1ad760dc3fc8c142d8cec600652a4eedb4157d74aa6dc667894c704a86672d4"
```

### Success Response (200 OK)

If a new image is available, the server will respond with a JSON object containing the image metadata.

```json
{
  "available": true,
  "arquivo": "2024-01-26_10-30-00.png",
  "dia": "2024-01-26",
  "horario": "10:30:00",
  "versao": "2024-01-26_1"
}
```

### Not Found Response (200 OK)

If no image is available, the server will respond with:

```json
{
  "available": false
}
```

---

## 2. Download Image

This endpoint allows you to download the latest available image.

- **URL:** `/api/image`
- **Method:** `GET`
- **Authentication:** Bearer Token

### Example Request (curl)

Replace `<YOUR_TOKEN>` with your actual Bearer token. This command will save the image to a file named `latest_image.png`.

```bash
curl -X GET http://eink.mandates.chat/api/image \
  -H "Authorization: Bearer b1ad760dc3fc8c142d8cec600652a4eedb4157d74aa6dc667894c704a86672d4" \
  --output latest_image.png
```

### Success Response (200 OK)

The server will respond with the image data (`image/png`).

### Not Found Response (404 Not Found)

If no image is available to download, the server will respond with a JSON error.

```json
{
  "error": "No image available"
}
```
