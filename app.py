from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

DEFAULT_SHEET_ID = "1lJznRnmCxV6ulrVsMBbnVi1qD-FCOapLfh3Hv7fxNoE"
DEFAULT_WORKSHEET = "cardapio"
SHEET_COLUMNS = [
    "dia",
    "data",
    "prato_principal",
    "acompanhamento",
    "salada",
    "sobremesa",
    "aviso",
    "ultima_atualizacao",
]
WEEKDAY_OPTIONS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


@dataclass(frozen=True)
class AppConfig:
    sheet_id: str
    worksheet_name: str


@dataclass(frozen=True)
class AuthConfig:
    username: str
    password: str

    @property
    def is_configured(self) -> bool:
        return bool(self.username.strip() and self.password.strip())


def get_secret_value(key: str, default: str = "") -> str:
    """Busca uma chave simples no st.secrets ou em variável de ambiente."""
    if key in st.secrets:
        return str(st.secrets[key])
    return os.getenv(key, default)


def get_auth_config() -> AuthConfig:
    """Carrega login/senha sem deixar credenciais hardcoded no GitHub."""
    auth_section = st.secrets.get("auth", {}) if hasattr(st, "secrets") else {}

    username = ""
    password = ""

    if isinstance(auth_section, dict):
        username = str(auth_section.get("username", "")).strip()
        password = str(auth_section.get("password", "")).strip()

    username = username or get_secret_value("ADMIN_USERNAME").strip()
    password = password or get_secret_value("ADMIN_PASSWORD").strip()

    return AuthConfig(username=username, password=password)


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state.pop("auth_username", None)
    st.rerun()


def authenticate(username: str, password: str, auth_config: AuthConfig) -> bool:
    """Compara credenciais usando comparação constante."""
    username_ok = hmac.compare_digest(username.strip(), auth_config.username)
    password_ok = hmac.compare_digest(password.strip(), auth_config.password)
    return username_ok and password_ok


def require_login() -> None:
    """Bloqueia o painel administrativo até o usuário autenticar."""
    auth_config = get_auth_config()

    if not auth_config.is_configured:
        st.error("Login administrativo não configurado.")
        st.info(
            "Configure ADMIN_USERNAME e ADMIN_PASSWORD nos Secrets do Streamlit Cloud "
            "ou no arquivo .streamlit/secrets.toml local."
        )
        st.stop()

    if st.session_state.get("authenticated") is True:
        return

    st.title("Acesso administrativo")
    st.caption("Entre para editar o cardápio semanal.")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if submitted:
        if authenticate(username, password, auth_config):
            st.session_state["authenticated"] = True
            st.session_state["auth_username"] = username.strip()
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

    st.stop()


def _load_service_account_info() -> dict[str, Any]:
    if "gcp_service_account" in st.secrets:
        return dict(st.secrets["gcp_service_account"])

    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        return json.loads(raw_json)

    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if json_path:
        with open(json_path, "r", encoding="utf-8") as file:
            return json.load(file)

    raise RuntimeError(
        "Credenciais não configuradas. Defina st.secrets['gcp_service_account'], "
        "GOOGLE_SERVICE_ACCOUNT_JSON ou GOOGLE_SERVICE_ACCOUNT_FILE."
    )


@st.cache_resource(show_spinner=False)
def get_gspread_client() -> gspread.Client:
    credentials = Credentials.from_service_account_info(
        _load_service_account_info(),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(credentials)


@st.cache_data(show_spinner=False, ttl=30)
def load_menu_dataframe(sheet_id: str, worksheet_name: str) -> pd.DataFrame:
    worksheet = get_gspread_client().open_by_key(sheet_id).worksheet(worksheet_name)
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=SHEET_COLUMNS)

    dataframe = pd.DataFrame(records)
    for column in SHEET_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""

    return dataframe[SHEET_COLUMNS].fillna("")


def save_menu_dataframe(config: AppConfig, dataframe: pd.DataFrame) -> None:
    worksheet = get_gspread_client().open_by_key(config.sheet_id).worksheet(
        config.worksheet_name
    )

    normalized = dataframe.copy()
    normalized = normalized.fillna("")
    normalized = normalized[SHEET_COLUMNS]
    rows = [SHEET_COLUMNS] + normalized.astype(str).values.tolist()
    worksheet.clear()
    worksheet.update("A1", rows, value_input_option="USER_ENTERED")
    load_menu_dataframe.clear()


def validate_dataframe(dataframe: pd.DataFrame) -> list[str]:
    errors: list[str] = []

    for index, row in dataframe.reset_index(drop=True).iterrows():
        row_number = index + 2
        if not any(str(value).strip() for value in row.values):
            continue

        weekday = str(row["dia"]).strip()
        date_value = str(row["data"]).strip()
        updated_at = str(row["ultima_atualizacao"]).strip()

        if weekday and weekday not in WEEKDAY_OPTIONS:
            errors.append(f"Linha {row_number}: dia inválido '{weekday}'.")

        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            errors.append(
                f"Linha {row_number}: data deve estar no formato YYYY-MM-DD."
            )

        if updated_at:
            try:
                datetime.strptime(updated_at, "%H:%M")
            except ValueError:
                errors.append(
                    f"Linha {row_number}: última atualização deve estar no formato HH:MM."
                )

    return errors


def build_default_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dia": "Seg",
                "data": "2026-04-27",
                "prato_principal": "Frango grelhado",
                "acompanhamento": "Arroz, feijão e purê",
                "salada": "Alface e tomate",
                "sobremesa": "Fruta",
                "aviso": "Cardápio sujeito a alterações.",
                "ultima_atualizacao": "08:15",
            }
        ],
        columns=SHEET_COLUMNS,
    )


def render_sidebar() -> AppConfig:
    with st.sidebar:
        st.header("Configuração")
        sheet_id = st.text_input("ID da planilha", value=DEFAULT_SHEET_ID)
        worksheet_name = st.text_input("Nome da aba", value=DEFAULT_WORKSHEET)
        st.markdown(
            "Compartilhe a planilha com o e-mail do service account como **Editor**."
        )

        st.divider()
        logged_user = st.session_state.get("auth_username", "administrador")
        st.caption(f"Logado como: **{logged_user}**")
        st.button("Sair", use_container_width=True, on_click=logout)

    return AppConfig(sheet_id=sheet_id.strip(), worksheet_name=worksheet_name.strip())


def render_editor(dataframe: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Editar cardápio")
    return st.data_editor(
        dataframe,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "dia": st.column_config.SelectboxColumn(
                "Dia",
                options=WEEKDAY_OPTIONS,
                required=True,
            ),
            "data": st.column_config.TextColumn("Data", help="Formato YYYY-MM-DD"),
            "prato_principal": st.column_config.TextColumn("Prato principal"),
            "acompanhamento": st.column_config.TextColumn("Acompanhamento"),
            "salada": st.column_config.TextColumn("Salada"),
            "sobremesa": st.column_config.TextColumn("Sobremesa"),
            "aviso": st.column_config.TextColumn("Aviso", width="large"),
            "ultima_atualizacao": st.column_config.TextColumn(
                "Última atualização",
                help="Formato HH:MM",
            ),
        },
    )


def main() -> None:
    st.set_page_config(
        page_title="Painel do Cardápio",
        page_icon="🥗",
        layout="wide",
    )

    require_login()

    st.title("Painel Administrativo do Cardápio")
    st.caption("Edite a aba do Google Sheets e salve sem abrir a planilha manualmente.")

    config = render_sidebar()

    if not config.sheet_id or not config.worksheet_name:
        st.warning("Informe o ID da planilha e o nome da aba.")
        st.stop()

    try:
        dataframe = load_menu_dataframe(config.sheet_id, config.worksheet_name)
    except Exception as error:  # noqa: BLE001
        st.error(f"Não foi possível abrir a planilha: {error}")
        st.info(
            "Confira as credenciais do Google e se a aba existe com permissão de edição."
        )
        st.stop()

    if dataframe.empty:
        dataframe = build_default_dataframe()

    edited = render_editor(dataframe)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Salvar na planilha", type="primary", use_container_width=True):
            errors = validate_dataframe(edited)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    save_menu_dataframe(config, edited)
                except Exception as error:  # noqa: BLE001
                    st.error(f"Erro ao salvar: {error}")
                else:
                    st.success("Planilha atualizada com sucesso.")

    with col2:
        if st.button("Recarregar dados", use_container_width=True):
            load_menu_dataframe.clear()
            st.rerun()

    st.subheader("Prévia CSV")
    st.code(edited.to_csv(index=False), language="csv")


if __name__ == "__main__":
    main()
