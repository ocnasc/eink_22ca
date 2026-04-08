# PLANO DE AÇÃO — eink_22ca

> Baseado na análise dos requisitos funcionais (`requisitos.md`) e do estado atual do projeto.

---

## Estado Atual

| RF | Título | Status |
|----|--------|--------|
| RF01 | Álbum de fotos (GET/POST/DELETE) | Não implementado |
| RF02 | Scheduler automático configurável sem repetição | Parcialmente implementado |
| RF03 | Envio direto de foto sem overlay | Não implementado |
| RF04 | Botão ON/OFF do scheduler | Não implementado |
| RF05 | Melhora do frontend | Parcialmente implementado |
| RF06 | Álbum de mensagens/submensagens | Não implementado |
| RF07 | Dark mode no scheduler | Implementado |
| RF08 | Manter `/api/status` e `/api/image` | Implementado |

---

## Etapas de Implementação

### Etapa 1 — Backend: Álbum de Fotos (RF01)

**Objetivo:** Persistir as fotos enviadas em um "álbum" gerenciável via API.

**Arquivos afetados:** `app.py`, `data/`

**Tarefas:**
- Criar `data/album.json` para armazenar metadados das fotos (id, filename, path, created_at)
- Implementar endpoint `GET /api/album` — retorna lista de fotos do álbum
- Implementar endpoint `POST /api/album` — adiciona uma foto ao álbum (multipart/form-data)
- Implementar endpoint `DELETE /api/album/<id>` — remove uma foto do álbum e o arquivo físico
- Ao fazer upload via formulário principal, a foto já deve ser adicionada ao álbum automaticamente

---

### Etapa 2 — Backend: Álbum de Mensagens (RF06)

**Objetivo:** Persistir pares mensagem/submensagem para reutilização.

**Arquivos afetados:** `app.py`, `data/`

**Tarefas:**
- Criar `data/messages.json` para armazenar pares `{ id, frase_superior, frase_inferior, created_at }`
- Implementar endpoint `GET /api/messages` — lista todas as mensagens
- Implementar endpoint `POST /api/messages` — adiciona um par mensagem/submensagem
- Implementar endpoint `DELETE /api/messages/<id>` — remove um par

---

### Etapa 3 — Backend: Scheduler Automático Configurável (RF02 + RF04 + RF07)

**Objetivo:** Substituir o scheduler manual por um scheduler automático que itera sobre o álbum de fotos sem repetir imagem ou mensagem, com intervalo configurável e botão ON/OFF.

**Arquivos afetados:** `app.py`, `data/`

**Tarefas:**
- Criar `data/auto_scheduler.json` com a configuração:
  ```json
  {
    "enabled": false,
    "interval_hours": 1,
    "dark_mode": false,
    "last_photo_id": null,
    "last_message_id": null
  }
  ```
- Implementar lógica de seleção **sem repetição**: ao executar, escolher foto e mensagem que não sejam as mesmas do ciclo anterior (controle via `last_photo_id` e `last_message_id`)
- Quando todas as fotos/mensagens tiverem sido usadas, reiniciar o ciclo
- Implementar endpoint `POST /api/auto-scheduler/config` — atualiza intervalo, dark_mode
- Implementar endpoint `POST /api/auto-scheduler/toggle` — liga/desliga (`enabled: true/false`)
- Implementar endpoint `GET /api/auto-scheduler/status` — retorna configuração atual
- Adaptar `scheduler_worker()` para verificar e executar o scheduler automático além dos jobs manuais

---

### Etapa 4 — Backend: Envio Direto Sem Overlay (RF03)

**Objetivo:** Permitir envio de uma foto diretamente como imagem final, sem aplicar o frame/overlay.

**Arquivos afetados:** `app.py`, `picture.py`

**Tarefas:**
- Adicionar parâmetro `raw: bool` em `process_image_generation_from_path()`
- Quando `raw=True`: redimensionar a foto para 800×480 e salvar diretamente (sem texto, sem overlay)
- Adicionar endpoint `POST /api/send-raw` — recebe `foto_id` (do álbum) ou upload direto, gera sem overlay
- Adicionar botão "Enviar Foto Direta" no frontend (sem mensagem)

---

### Etapa 5 — Frontend: Melhorias de UI (RF05)

**Objetivo:** Melhorar a usabilidade e tornar visíveis os novos recursos no frontend. Incluindo página de login

**Arquivos afetados:** `templates/index.html`

**Tarefas:**
- **Seção Álbum de Fotos:**
  - Galeria visual com miniaturas das fotos cadastradas
  - Botão para selecionar uma foto do álbum (em vez de sempre fazer upload)
  - Botão de exclusão por foto
- **Seção Álbum de Mensagens:**
  - Lista de pares mensagem/submensagem salvos
  - Botão para selecionar um par salvo e preencher o formulário automaticamente
  - Botão de adicionar e excluir mensagens
- **Seção Scheduler Automático:**
  - Toggle ON/OFF visível (RF04)
  - Campo para configurar intervalo em horas
  - Checkbox dark mode
  - Status atual (próxima execução, última foto usada)
- **Seção Envio Direto:**
  - Botão "Enviar Foto Direta" que envia sem overlay (RF03)
- **Geral:**
  - Layout com abas ou seções colapsáveis para organizar as funcionalidades
  - Indicação visual do status do scheduler (ativo/inativo)

---

## Ordem de Execução Recomendada

```
1. Etapa 1 — Álbum de fotos (base para as outras etapas)
2. Etapa 2 — Álbum de mensagens (base para o scheduler automático)
3. Etapa 3 — Scheduler automático (depende das etapas 1 e 2)
4. Etapa 4 — Envio direto sem overlay (independente)
5. Etapa 5 — Frontend (consolida tudo visualmente)
```

---

## Restrições e Invariantes

- **RF08:** As rotas `/api/status` e `/api/image` devem continuar retornando exatamente o mesmo formato atual — nenhuma alteração nessas rotas.
- **Autenticação:** Manter os decoradores `login_required` (sessão) e `bearer_token_required` (API) em todos os endpoints novos, conforme o contexto.
- **Armazenamento:** Continuar usando JSON em `data/` (sem introduzir banco de dados).
- **Compatibilidade Docker:** Não alterar a estrutura de `Dockerfile` ou `requirements.txt` além do estritamente necessário.
