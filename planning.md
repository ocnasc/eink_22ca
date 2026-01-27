# Planning – API de Geração e Distribuição de Imagens

## Objetivo
Criar um serviço simples em Python que gere uma imagem a partir de uma foto + textos, salve o arquivo com timestamp em GMT-3, versione por dia e disponibilize a imagem via API para consumo por um Raspberry Pi.

---

## Visão Geral do Fluxo

1. Usuário (web/local) envia:
   - Foto
   - Frase superior
   - Frase inferior
   - Dark mode (opcional)

2. Backend:
   - Gera imagem com Pillow
   - Calcula data/hora em GMT-3
   - Define versão incremental por dia
   - Salva imagem em disco
   - Atualiza arquivo JSON de estado

3. Raspberry Pi:
   - Consulta status da API
   - Compara versão local vs remota
   - Baixa imagem apenas se houver nova versão

---

## Estrutura de Diretórios

```
project/
│
├─ app.py                # Flask API
├─ picture.py            # Lógica de geração da imagem
│
├─ data/
│   ├─ latest.json       # Estado atual (última imagem gerada)
│   └─ history/          # Histórico de versões (opcional)
│
├─ static/
│   └─ images/           # Imagens geradas
│
├─ uploads/              # Uploads temporários
```

---

## Regras de Nomeação de Arquivo

- Formato do nome da imagem:

```
YYYY-MM-DD_HH-MM-SS.png
```

- Horário sempre em **GMT-3**

Exemplo:
```
2026-01-23_08-41-22.png
```

---

## Versionamento

- A versão é baseada no dia ISO:

```
YYYY-MM-DD_N
```

- Onde `N` é incremental a cada nova geração no mesmo dia

Exemplo:
```
2026-01-23_1
2026-01-23_2
2026-01-23_3
```

### Regras
- Se não existir versão para o dia atual → começar em `_1`
- Se já existir → incrementar
- Versão atual fica registrada em `data/latest.json`

---

## Arquivo de Metadata (JSON)

Arquivo: `data/latest.json`

Formato:
```json
{
  "dia": "2026-01-23",
  "horario": "08:41:22",
  "versao": "2026-01-23_3",
  "arquivo": "2026-01-23_08-41-22.png"
}
```

### Observações
- `dia` e `horario` referem-se ao momento da geração (GMT-3)
- `versao` é usada pelo Raspberry para detectar atualizações
- `arquivo` aponta para a imagem em `static/images/`

---

## Endpoints da API

### 1. Gerar imagem

**POST** `/api/generate`

Payload (multipart/form-data):
- `foto` (file)
- `frase_superior` (string)
- `frase_inferior` (string)
- `dark_mode` (`true` | `false`)

Ações:
- Salva upload temporário
- Gera imagem final
- Atualiza versão
- Atualiza `latest.json`

Resposta:
```json
{
  "ok": true,
  "versao": "2026-01-23_3"
}
```

---

### 2. Status (para Raspberry)

**GET** `/api/status`

Resposta quando não há imagem:
```json
{
  "disponivel": false
}
```

Resposta quando há imagem:
```json
{
  "disponivel": true,
  "dia": "2026-01-23",
  "horario": "08:41:22",
  "versao": "2026-01-23_3",
  "arquivo": "2026-01-23_08-41-22.png"
}
```

---

### 3. Download da imagem

**GET** `/api/image`

- Retorna a imagem correspondente ao `latest.json`
- `Content-Type: image/png`

---

## Lógica do Cliente (Raspberry Pi)

1. Fazer `GET /api/status`
2. Comparar `versao` com a versão local
3. Se diferente:
   - Fazer `GET /api/image`
   - Salvar imagem localmente
   - Atualizar versão local
4. Atualizar display

---

## Considerações Técnicas

- Serviço pensado para **uso pessoal**
- Não há autenticação inicialmente
- Escopo reduzido e controlado
- Estrutura preparada para:
  - adicionar token simples
  - adicionar checksum
  - limpeza de imagens antigas

---

## Próximos Passos (opcional)

- [ ] Script cliente para Raspberry Pi
- [ ] Executar Flask como service
- [ ] Dockerizar aplicação
- [ ] Endpoint de histórico
- [ ] Endpoint de health check

