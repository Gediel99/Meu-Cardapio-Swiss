# Painel Streamlit

Painel público e administrativo para exibir o cardápio da semana, editar a aba `cardapio` do Google Sheets e publicar tudo no Streamlit Cloud.

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

[auth.admin]
username = "admin"
password = "sua-senha-forte"

[auth.user]
username = "funcionario"
password = "sua-senha-forte"
```

## 3. Rodar localmente

```bash
streamlit run app.py
```

## 4. Perfis de acesso

Também aceita variáveis de ambiente:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `USER_USERNAME`
- `USER_PASSWORD`
- `COMMON_USERNAME`
- `COMMON_PASSWORD`

## 5. O que cada perfil vê

- `admin`: edição rápida, tabela completa, prévia do app, CSV, usuários e modelos
- `user`: apenas edição rápida e prévia do app

## 6. Cadastro de funcionários no painel

Quando você entra como `admin`, aparece uma aba `Usuários`.

Nela você consegue:

- cadastrar um novo login
- criar o acesso sempre como `Usuário comum`
- promover depois para `Administrador` se quiser
- gravar esse acesso na aba `usuarios` da mesma planilha

As senhas são salvas no formato hash e os usuários cadastrados passam a funcionar também no Streamlit Cloud.

## 7. Modelos de refeição e campos extras

Na aba `Modelos e campos`, o administrador consegue:

- cadastrar refeições prontas como `Strogonoff`
- salvar prato principal, acompanhamento, salada, sobremesa e aviso
- aplicar esse modelo depois na `Edição rápida`
- criar colunas extras na planilha quando precisar guardar uma informação nova

## 8. Preparar próxima semana

No topo do painel, o administrador agora tem um botão `Preparar próxima semana`.

Ele:

- cria automaticamente segunda a sexta da próxima semana
- limpa os campos de prato, acompanhamento, salada e sobremesa
- mantém o aviso padrão

Assim você não precisa montar a estrutura da semana nova à mão.

## 9. Downloads do aplicativo

A home pública do Streamlit pode mostrar arquivos prontos para download quando eles estiverem dentro da pasta:

```text
releases/
```

Hoje foram preparados estes nomes:

- `MyCardapioSwiss-android-release.apk`
- `MyCardapioSwiss-windows-release.zip`

## 10. Assinatura e confiança

Para Android, o ideal é gerar a release com seu próprio keystore.

No Flutter app, foi deixado pronto o suporte a:

```text
android/key.properties
```

Use o modelo:

```text
android/key.properties.example
```

Importante:

- sem assinatura própria, o Android ainda consegue instalar, mas não é o cenário ideal para distribuição profissional
- no Windows, aviso do SmartScreen não some só por “buildar”; o caminho certo é assinar o instalador com certificado digital de código
