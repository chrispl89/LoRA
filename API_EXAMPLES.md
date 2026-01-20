# Przykłady użycia API

## Health Check

```bash
curl http://localhost:8000/health
```

## 1. Utworzenie profilu osoby

```bash
curl -X POST http://localhost:8000/v1/persons \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "consent_confirmed": true,
    "subject_is_adult": true
  }'
```

## 2. Lista profili

```bash
curl http://localhost:8000/v1/persons
```

## 3. Pobranie presigned URL do uploadu zdjęcia

```bash
curl -X POST http://localhost:8000/v1/persons/1/uploads/presign \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "photo.jpg",
    "content_type": "image/jpeg",
    "size_bytes": 1024000
  }'
```

Odpowiedź:
```json
{
  "url": "http://localhost:9000/lora-person-data/uploads/1/photo.jpg?...",
  "method": "PUT",
  "key": "uploads/1/photo.jpg",
  "content_type": "image/jpeg"
}
```

## 4. Upload zdjęcia do S3

```bash
# Użyj URL z poprzedniego kroku
curl -X PUT "http://localhost:9000/lora-person-data/uploads/1/photo.jpg?..." \
  -H "Content-Type: image/jpeg" \
  --data-binary @photo.jpg
```

## 5. Rejestracja zdjęcia

```bash
curl -X POST http://localhost:8000/v1/persons/1/photos/complete \
  -H "Content-Type: application/json" \
  -d '{
    "key": "uploads/1/photo.jpg",
    "content_type": "image/jpeg",
    "size_bytes": 1024000
  }'
```

## 6. Rozpoczęcie preprocessing

```bash
curl -X POST http://localhost:8000/v1/persons/1/preprocess
```

## 7. Utworzenie modelu (trening)

```bash
curl -X POST http://localhost:8000/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 1,
    "name": "John Doe Model v1",
    "base_model_name": "runwayml/stable-diffusion-v1-5",
    "trigger_token": "sks person",
    "train_config": {
      "steps": 1000,
      "learning_rate": 0.0001,
      "rank": 16
    }
  }'
```

## 8. Lista modeli

```bash
curl http://localhost:8000/v1/models?person_id=1
```

## 9. Szczegóły modelu

```bash
curl http://localhost:8000/v1/models/1
```

## 10. Generowanie obrazu

```bash
curl -X POST http://localhost:8000/v1/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model_version_id": 1,
    "prompt": "sks person in a garden, high quality",
    "negative_prompt": "blurry, low quality",
    "steps": 50,
    "width": 512,
    "height": 512,
    "seed": 42
  }'
```

## 11. Status generacji

```bash
curl http://localhost:8000/v1/generations/1
```

Odpowiedź zawiera presigned URL do wygenerowanego obrazu:
```json
{
  "id": 1,
  "status": "completed",
  "output_url": "http://localhost:9000/lora-person-data/outputs/1.png?...",
  "thumbnail_url": "http://localhost:9000/lora-person-data/outputs/thumbnails/1.png?..."
}
```

## 12. Usunięcie danych osoby

```bash
curl -X DELETE http://localhost:8000/v1/persons/1
```

## Błędy i walidacje

### Brak zgody
```bash
curl -X POST http://localhost:8000/v1/persons \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test",
    "consent_confirmed": false,
    "subject_is_adult": true
  }'
# Zwraca 400: "consent_confirmed must be true"
```

### Blokada promptu (guardrails)
```bash
curl -X POST http://localhost:8000/v1/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model_version_id": 1,
    "prompt": "child playing in garden"
  }'
# Zwraca 400: "Prompt contains blocked keywords"
```
