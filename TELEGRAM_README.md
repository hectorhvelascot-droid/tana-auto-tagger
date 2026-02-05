# 🤖 Telegram Bot - Guía Rápida

## Configuración

Tu bot ya está configurado con:
- **Token:** Configurado en `.env`
- **Username autorizado:** Hector Velasco
- **Modo:** Polling (desarrollo local)

## Cómo Probar Localmente

### 1. Iniciar el Bot

```bash
python run_telegram_bot.py
```

Verás:
```
INFO - Starting Telegram Bot in TEST MODE (polling)...
INFO - Allowed username: Hector Velasco
INFO - Bot is running! Press Ctrl+C to stop.
```

### 2. Comandos Disponibles en Telegram

Escribe a tu bot en Telegram:

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/start` | Inicia el bot y muestra ayuda | `/start` |
| `/sync <fechas>` | Sincroniza notas | `/sync hoy` |
| `/status` | Ver estado de sesión | `/status` |
| `/cancel` | Cancelar operación | `/cancel` |
| `/help` | Mostrar ayuda | `/help` |

### 3. Formatos de Fechas Soportados

```
/sync hoy              → Solo hoy
/sync ayer             → Solo ayer
/sync últimos 3 días   → Últimos 3 días
/sync esta semana      → Desde lunes hasta hoy
/sync 2024-02-01 2024-02-05  → Rango específico
```

### 4. Flujo de Uso

1. Escribe: `/sync hoy`
2. Bot responde: "✅ Solicitud recibida..."
3. Usa `/status` para ver el estado
4. En producción, recibirás notificación cuando esté listo

## Arquitectura

```
Telegram (Usuario)
    ↓
Telegram Bot (python-telegram-bot)
    ↓
FastAPI API (/telegram/* endpoints)
    ↓
Tana Input API (localhost:1111)
```

## Archivos del Sistema

- `telegram_bot.py` - Handlers del bot
- `telegram_models.py` - Modelos de datos
- `session_manager.py` - Gestión de sesiones
- `date_parser.py` - Parseo de fechas
- `run_telegram_bot.py` - Script de prueba local

## Deploy en Render (Próximo Paso)

Para producción:
1. Cambiar `TELEGRAM_USE_WEBHOOK=true` en `.env`
2. Configurar `TELEGRAM_WEBHOOK_URL` con URL de Render
3. Deploy con `git push`
4. Configurar webhook con BotFather

## Troubleshooting

**"No tienes permiso"**
- Verifica que tu username en Telegram coincida con `TELEGRAM_ALLOWED_USERNAME`

**Bot no responde**
- Verifica que el token sea correcto
- Asegúrate de haber iniciado el bot con `/start`

**Error de importación**
```bash
pip install python-telegram-bot dateparser
```

## Variables de Entorno

```env
TELEGRAM_BOT_TOKEN=8330377932:AAHKbPMWf-W5Wyht95I-RideMKhGxJqkVUU
TELEGRAM_ALLOWED_USERNAME=Hector Velasco
TELEGRAM_USE_WEBHOOK=false  # true para producción
TELEGRAM_WEBHOOK_URL=https://tana-tagger.onrender.com/telegram/webhook
```
