# Tana Auto-Tagger

Herramienta para clasificar automáticamente notas sin tags en Tana usando AI local (sentence-transformers).

## 🚀 Instalación

```bash
cd tana-auto-tagger

# Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -e .
```

La primera ejecución descargará el modelo de embeddings (~80MB).

## 📋 Flujo de Uso

### 1. Sincronizar con Tana (Automático)

Asegúrate de que Tana esté abierto y ejecuta:

```bash
tana-tagger sync --days 7
```

Esto actualizará automáticamente el catálogo de tags y las notas sin tags de los últimos 7 días en el caché local.

> [!NOTE]
> Este paso reemplaza la necesidad de copiar manualmente los resultados de Antigravity MCP. Requiere que el servidor local de Tana esté activo (usualmente en el puerto 1111).

### 2. Procesar con AI

```bash
# Ver estado actual
tana-tagger status

# Procesar en modo interactivo
tana-tagger process --days 7 --interactive

# Solo ver sugerencias sin aplicar
tana-tagger process --dry-run
```

```bash
# Ver estado actual
tana-tagger status

# Procesar en modo interactivo
tana-tagger process --days 7 --interactive

# Solo ver sugerencias sin aplicar
tana-tagger process --dry-run
```

### 4. Aplicar Tags

Después de revisar, ver asignaciones pendientes:
```bash
tana-tagger apply
```

Luego ejecuta los comandos MCP mostrados en Antigravity.

## 🌐 API (Webhook)

Para uso programático:

```bash
# Iniciar servidor
uvicorn tana_auto_tagger.api:app --reload --port 8000
```

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/status` | Estado del caché |
| POST | `/process` | Clasificar notas y obtener sugerencias |
| POST | `/apply` | Obtener comando MCP para aplicar tag |
| POST | `/cache/tags` | Actualizar caché de tags |
| POST | `/cache/notes` | Actualizar caché de notas |

### Ejemplo: Procesar Notas

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"days_back": 7, "top_k": 3}'
```

## ⚙️ Configuración

Edita `.env`:

```env
TANA_WORKSPACE_ID=8YR1337hvC
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Tags de sistema a excluir (IDs separados por coma)
EXCLUDED_TAG_IDS=JM0aEWBmpI,NzXZM4Ge78,veL3TgH_uX,VUEjgCXD0ARq
```

## 📁 Estructura

```
tana-auto-tagger/
├── .cache/                  # Datos en caché
│   ├── tags.json
│   ├── notes.json
│   └── pending_assignments.json
├── tana_auto_tagger/
│   ├── __init__.py
│   ├── api.py              # Endpoints FastAPI
│   ├── classifier.py       # AI con sentence-transformers
│   ├── cli.py              # Interfaz de línea de comandos
│   ├── config.py           # Configuración desde .env
│   ├── models.py           # Modelos de datos
│   ├── reviewer.py         # Revisión interactiva
│   └── tana_client.py      # Utilidades para Tana
├── .env
├── .env.example
├── pyproject.toml
└── README.md
```
