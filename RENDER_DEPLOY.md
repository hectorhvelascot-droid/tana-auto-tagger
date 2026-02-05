# Tana Auto-Tagger - Telegram Bot

## Deploy en Render

### 1. Preparar el código

```bash
# Asegúrate de tener todo en git
git add .
git commit -m "Add Telegram Bot integration"
git push origin main
```

### 2. Crear Web Service en Render

1. Ve a https://dashboard.render.com
2. Click "New" → "Web Service"
3. Conecta tu repositorio de GitHub
4. Configura:
   - **Name**: tana-auto-tagger
   - **Environment**: Python 3
   - **Build Command**: `pip install -e .`
   - **Start Command**: `python -m tana_auto_tagger.webhook_server`
   - **Plan**: Free

### 3. Variables de Entorno

En Render Dashboard → tu servicio → Environment, agrega:

```
TANA_WORKSPACE_ID=8YR1337hvC
TANA_LOCAL_URL=http://localhost:1111
EMBEDDING_MODEL=all-MiniLM-L6-v2
EXCLUDED_TAG_IDS=JM0aEWBmpI,NzXZM4Ge78,veL3TgH_uX,VUEjgCXD0ARq
TELEGRAM_BOT_TOKEN=8330377932:AAEjkeQLVqBjg7SkkMukFlnMfRASf6Z5wck
TELEGRAM_ALLOWED_USERNAME=5960833907
TELEGRAM_USE_WEBHOOK=true
TELEGRAM_WEBHOOK_URL=https://tana-auto-tagger.onrender.com/webhook
RENDER_EXTERNAL_URL=https://tana-auto-tagger.onrender.com
```

### 4. Configurar Webhook

Una vez deployado, el bot se auto-configura con webhook.

Para verificar:
```bash
curl https://api.telegram.org/botTU_TOKEN/getWebhookInfo
```

### 5. Probar

Envía `/start` a tu bot en Telegram.

## Comandos disponibles

- `/start` - Iniciar bot
- `/sync <fechas>` - Sincronizar notas
- `/status` - Ver estado
- `/cancel` - Cancelar

## Notas

- Tana Input API debe estar accesible desde tu red local
- El bot usa sesiones en memoria (30 min TTL)
- Para persistencia entre reinicios, agregar Redis
