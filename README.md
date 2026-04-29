# Painel Streamlit

Painel administrativo para editar a aba `cardapio` do Google Sheets e publicar no Streamlit Cloud.

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

[auth]
username = "admin"
password = "sua-senha-forte"
```

## 3. Rodar localmente

```bash
streamlit run app.py
```

## 4. Perfis de acesso

Você pode configurar dois perfis:

```toml
[auth.admin]
username = "admin"
password = "senha-admin"

[auth.user]
username = "funcionario"
password = "senha-funcionario"
```

Também aceita variáveis de ambiente:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `COMMON_USERNAME`
- `COMMON_PASSWORD`

## 5. O que cada perfil vê

- `admin`: edição rápida, tabela completa, prévia do app, CSV e configuração da planilha
- `user`: apenas edição rápida e prévia do app
