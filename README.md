# Painel Streamlit

Painel simples para editar a aba `cardapio` do Google Sheets sem abrir a planilha manualmente.

## 1. Instalar dependências

```bash
pip install -r requirements.txt
```

## 2. Configurar credenciais Google

Crie um Service Account no Google Cloud com acesso ao Google Sheets API e compartilhe a planilha com o e-mail dessa conta como **Editor**.

Você pode configurar de um destes jeitos:

### Opção A: arquivo JSON

```bash
set GOOGLE_SERVICE_ACCOUNT_FILE=C:\caminho\service-account.json
```

### Opção B: JSON em variável de ambiente

```bash
set GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account", ...}
```

### Opção C: `st.secrets`

Crie `.streamlit/secrets.toml`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "seu-projeto"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

## 3. Rodar

```bash
streamlit run app.py
```

## 4. O que o painel faz

- carrega a aba `cardapio`
- permite editar, adicionar e remover linhas
- valida `data` em `YYYY-MM-DD`
- valida `ultima_atualizacao` em `HH:MM`
- salva tudo de volta na planilha
