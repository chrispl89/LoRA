# Frontend

Next.js frontend dla LoRA Person MVP.

## Uruchomienie

```bash
# Instalacja
npm install

# Dev server
npm run dev

# Build
npm run build
npm start
```

## Struktura

```
frontend/
├── app/              # Next.js app router
│   ├── page.tsx      # Home page
│   ├── persons/      # Person management
│   └── models/       # Model management
├── components/       # React components
└── types/            # TypeScript types
```

## Konfiguracja

Ustaw zmienną środowiskową:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Lub edytuj `next.config.js`.
