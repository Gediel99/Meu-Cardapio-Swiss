from __future__ import annotations

import hmac
import html
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
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
WEEKDAY_FULL_NAMES = {
    "Seg": "Segunda-feira",
    "Ter": "Terça-feira",
    "Qua": "Quarta-feira",
    "Qui": "Quinta-feira",
    "Sex": "Sexta-feira",
    "Sáb": "Sábado",
    "Dom": "Domingo",
}
MONTH_NAMES = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


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
    if key in st.secrets:
        return str(st.secrets[key])
    return os.getenv(key, default)


def get_auth_config() -> AuthConfig:
    auth_section = st.secrets.get("auth", {}) if hasattr(st, "secrets") else {}

    username = ""
    password = ""

    if isinstance(auth_section, dict):
        username = str(auth_section.get("username", "")).strip()
        password = str(auth_section.get("password", "")).strip()

    username = username or get_secret_value("ADMIN_USERNAME").strip()
    password = password or get_secret_value("ADMIN_PASSWORD").strip()

    return AuthConfig(username=username, password=password)


def authenticate(username: str, password: str, auth_config: AuthConfig) -> bool:
    username_ok = hmac.compare_digest(username.strip(), auth_config.username)
    password_ok = hmac.compare_digest(password.strip(), auth_config.password)
    return username_ok and password_ok


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state.pop("auth_username", None)
    st.rerun()


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top right, rgba(234, 246, 231, 0.95), transparent 32%),
                    linear-gradient(180deg, #f5fbf3 0%, #eff7ec 100%);
            }

            .block-container {
                max-width: 1160px;
                padding-top: 3.4rem;
                padding-bottom: 2rem;
            }

            [data-testid="stSidebar"] {
                background: #f7fbf5;
                border-right: 1px solid rgba(18, 63, 24, 0.08);
            }

            [data-testid="stSidebarContent"] {
                padding-top: 3.2rem;
            }

            div[data-testid="stButton"] > button,
            div[data-testid="stDownloadButton"] > button,
            div[data-testid="stFormSubmitButton"] > button {
                border-radius: 14px;
                font-weight: 700;
                min-height: 2.8rem;
                border: 1px solid rgba(18, 63, 24, 0.12);
                box-shadow: none;
            }

            div[data-testid="stButton"] > button[kind="primary"],
            div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
                background: linear-gradient(180deg, #3d9442 0%, #2f7d32 100%) !important;
                color: #ffffff !important;
                border: 1px solid #2f7d32 !important;
            }

            div[data-testid="stButton"] > button[kind="secondary"],
            div[data-testid="stDownloadButton"] > button {
                background: rgba(255, 255, 255, 0.96) !important;
                color: #37433a !important;
                border: 1px solid rgba(18, 63, 24, 0.14) !important;
            }

            div[data-testid="stButton"] > button:hover,
            div[data-testid="stDownloadButton"] > button:hover,
            div[data-testid="stFormSubmitButton"] > button:hover {
                border-color: #2f7d32 !important;
                color: #123f18 !important;
            }

            div[data-testid="stButton"] > button[kind="primary"]:hover,
            div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
                color: #ffffff !important;
                filter: brightness(1.02);
            }

            button[data-baseweb="tab"] {
                color: #4f5c53 !important;
                font-weight: 650 !important;
            }

            button[data-baseweb="tab"][aria-selected="true"] {
                color: #2f7d32 !important;
            }

            [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
                background-color: #2f7d32 !important;
            }

            div[data-testid="stDataFrame"] {
                border-radius: 18px;
                overflow: hidden;
                border: 1px solid rgba(18, 63, 24, 0.08);
            }

            .hero-card {
                padding: 1.3rem 1.4rem;
                border-radius: 24px;
                background: linear-gradient(135deg, #f2f9ef 0%, #ffffff 62%, #fff8ee 100%);
                border: 1px solid rgba(46, 125, 50, 0.12);
                box-shadow: 0 16px 44px rgba(18, 63, 24, 0.08);
                margin-bottom: 1rem;
            }

            .hero-top {
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                align-items: flex-start;
            }

            .hero-title {
                margin: 0;
                color: #123f18;
                font-size: 2rem;
                line-height: 1.06;
                font-weight: 850;
            }

            .hero-subtitle {
                margin-top: 0.45rem;
                color: #647067;
                font-size: 1rem;
                max-width: 40rem;
            }

            .hero-logo {
                min-width: 150px;
                text-align: right;
                color: #123f18;
                font-weight: 800;
                font-size: 1.05rem;
            }

            @media (max-width: 900px) {
                .hero-top {
                    flex-direction: column;
                }

                .hero-logo {
                    min-width: auto;
                    text-align: left;
                }

                .menu-row {
                    grid-template-columns: 1fr;
                    gap: 0.25rem;
                }
            }

            .sheet-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                padding: 0.42rem 0.75rem;
                border-radius: 999px;
                background: #eaf6e7;
                border: 1px solid rgba(46, 125, 50, 0.16);
                color: #2e7d32;
                font-size: 0.88rem;
                font-weight: 800;
                margin-top: 0.9rem;
            }

            .metric-card {
                padding: 1rem 1.05rem;
                border-radius: 18px;
                background: rgba(255, 255, 255, 0.92);
                border: 1px solid rgba(18, 63, 24, 0.08);
                box-shadow: 0 8px 22px rgba(0, 0, 0, 0.04);
                min-height: 98px;
            }

            .metric-label {
                color: #6a766d;
                font-size: 0.84rem;
                margin-bottom: 0.28rem;
            }

            .metric-value {
                color: #123f18;
                font-size: 1.42rem;
                font-weight: 850;
            }

            .panel-card {
                padding: 1rem 1.1rem;
                border-radius: 22px;
                background: rgba(255, 255, 255, 0.94);
                border: 1px solid rgba(18, 63, 24, 0.08);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
            }

            .panel-title {
                color: #123f18;
                font-size: 1.12rem;
                font-weight: 800;
                margin-bottom: 0.2rem;
            }

            .panel-subtitle {
                color: #687368;
                font-size: 0.92rem;
                margin-bottom: 0.9rem;
            }

            .preview-shell {
                padding: 1.1rem;
                border-radius: 24px;
                background: #ffffff;
                border: 1px solid rgba(46, 125, 50, 0.10);
                box-shadow: 0 16px 40px rgba(18, 63, 24, 0.06);
            }

            .day-chip-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin: 0.8rem 0 1rem 0;
            }

            .day-chip {
                padding: 0.5rem 0.75rem;
                border-radius: 14px;
                background: #ffffff;
                border: 1px solid rgba(18, 63, 24, 0.10);
                color: #5b675d;
                font-weight: 700;
                font-size: 0.9rem;
            }

            .day-chip.active {
                background: #eaf6e7;
                color: #2e7d32;
                border-color: rgba(46, 125, 50, 0.36);
            }

            .date-banner {
                padding: 0.82rem 0.95rem;
                border-radius: 16px;
                background: #eef8e9;
                color: #2e7d32;
                font-weight: 850;
                border: 1px solid rgba(46, 125, 50, 0.12);
                margin-bottom: 0.9rem;
            }

            .meal-card {
                padding: 1rem;
                border-radius: 18px;
                background: #ffffff;
                border: 1px solid rgba(0, 0, 0, 0.07);
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.04);
            }

            .meal-title {
                color: #df7317;
                font-size: 1.35rem;
                font-weight: 850;
                margin-bottom: 0.7rem;
            }

            .menu-row {
                display: grid;
                grid-template-columns: minmax(120px, 170px) 1fr;
                gap: 0.75rem;
                padding: 0.55rem 0;
                border-bottom: 1px solid rgba(0, 0, 0, 0.07);
            }

            .menu-row:last-child {
                border-bottom: none;
            }

            .menu-label {
                color: #5f6a61;
                font-weight: 650;
            }

            .menu-value {
                color: #182019;
                font-weight: 760;
            }

            .notice-card {
                padding: 0.9rem 1rem;
                margin-top: 0.9rem;
                border-radius: 16px;
                background: #fff8ea;
                border: 1px solid rgba(223, 115, 23, 0.16);
            }

            .notice-title {
                color: #cf6715;
                font-size: 1.05rem;
                font-weight: 850;
                margin-bottom: 0.2rem;
            }

            .soft-caption {
                color: #6c756d;
                font-size: 0.88rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> None:
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

    left, center, right = st.columns([1, 1.1, 1])
    with center:
        st.markdown(
            """
            <div class="hero-card">
                <div class="hero-title">Acesso administrativo</div>
                <div class="hero-subtitle">
                    Entre para editar o cardápio semanal com segurança.
                </div>
                <div class="sheet-pill">Painel protegido</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button(
                "Entrar",
                type="primary",
                use_container_width=True,
            )

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

    return normalize_dataframe(pd.DataFrame(records))


def normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    for column in SHEET_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    normalized = normalized[SHEET_COLUMNS].fillna("")
    for column in SHEET_COLUMNS:
        normalized[column] = normalized[column].astype(str).str.strip()
    return normalized


def save_menu_dataframe(config: AppConfig, dataframe: pd.DataFrame) -> None:
    worksheet = get_gspread_client().open_by_key(config.sheet_id).worksheet(
        config.worksheet_name
    )
    normalized = normalize_dataframe(dataframe)
    rows = [SHEET_COLUMNS] + normalized.astype(str).values.tolist()
    worksheet.clear()
    worksheet.update("A1", rows, value_input_option="USER_ENTERED")
    load_menu_dataframe.clear()


def validate_dataframe(dataframe: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    normalized = normalize_dataframe(dataframe)

    for index, row in normalized.reset_index(drop=True).iterrows():
        row_number = index + 2
        if not any(str(value).strip() for value in row.values):
            continue

        weekday = row["dia"]
        date_value = row["data"]
        updated_at = row["ultima_atualizacao"]

        if weekday and weekday not in WEEKDAY_OPTIONS:
            errors.append(f"Linha {row_number}: dia inválido '{weekday}'.")

        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Linha {row_number}: data deve estar no formato YYYY-MM-DD.")

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


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def format_display_date(weekday: str, iso_date: str) -> str:
    parsed = parse_iso_date(iso_date)
    weekday_name = WEEKDAY_FULL_NAMES.get(weekday, weekday or "Dia")
    month_name = MONTH_NAMES.get(parsed.month, "")
    return f"{weekday_name}, {parsed.day} de {month_name}"


def get_row_options(dataframe: pd.DataFrame) -> list[str]:
    options: list[str] = []
    for index, row in normalize_dataframe(dataframe).reset_index(drop=True).iterrows():
        weekday = row["dia"] or "Dia"
        iso_date = row["data"] or "sem-data"
        main_dish = row["prato_principal"] or "sem prato"
        options.append(f"{index} | {weekday} | {iso_date} | {main_dish}")
    return options


def render_sidebar() -> AppConfig:
    with st.sidebar:
        st.markdown("## Configuração")
        sheet_id = st.text_input("ID da planilha", value=DEFAULT_SHEET_ID)
        worksheet_name = st.text_input("Nome da aba", value=DEFAULT_WORKSHEET)
        st.info("Compartilhe a planilha com o e-mail do service account como Editor.")

        st.divider()
        logged_user = st.session_state.get("auth_username", "administrador")
        st.caption(f"Logado como: **{logged_user}**")
        st.button("Sair", use_container_width=True, on_click=logout)

    return AppConfig(sheet_id=sheet_id.strip(), worksheet_name=worksheet_name.strip())


def render_header() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-top">
                <div>
                    <div class="hero-title">Painel do Cardápio</div>
                    <div class="hero-subtitle">
                        Cadastre e atualize o almoço da semana sem abrir a planilha manualmente.
                    </div>
                </div>
                <div class="hero-logo">Swiss Park</div>
            </div>
            <div class="sheet-pill">Google Sheets conectado</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(dataframe: pd.DataFrame) -> None:
    normalized = normalize_dataframe(dataframe)
    total_days = len(normalized[normalized["data"].ne("")])
    filled_main_dishes = normalized["prato_principal"].ne("").sum()
    last_updates = [value for value in normalized["ultima_atualizacao"].tolist() if value]
    last_update = last_updates[-1] if last_updates else "-"

    col1, col2, col3 = st.columns(3)
    cards = [
        ("Dias cadastrados", str(total_days)),
        ("Pratos principais", str(filled_main_dishes)),
        ("Última atualização", last_update),
    ]

    for column, (label, value) in zip([col1, col2, col3], cards):
        with column:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{html.escape(label)}</div>
                    <div class="metric-value">{html.escape(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def initialize_draft(dataframe: pd.DataFrame, config: AppConfig) -> None:
    sheet_key = f"{config.sheet_id}:{config.worksheet_name}"
    if st.session_state.get("draft_sheet_key") != sheet_key:
        st.session_state["draft_sheet_key"] = sheet_key
        st.session_state["draft_df"] = normalize_dataframe(dataframe).copy()


def get_draft_dataframe() -> pd.DataFrame:
    draft = st.session_state.get("draft_df")
    if draft is None or not isinstance(draft, pd.DataFrame):
        draft = build_default_dataframe()
        st.session_state["draft_df"] = draft
    return normalize_dataframe(draft)


def set_draft_dataframe(dataframe: pd.DataFrame) -> None:
    st.session_state["draft_df"] = normalize_dataframe(dataframe).copy()


def render_quick_edit(dataframe: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Edição rápida por dia</div>
            <div class="panel-subtitle">
                Altere um dia específico sem mexer na tabela inteira.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    normalized = normalize_dataframe(dataframe).reset_index(drop=True)
    if normalized.empty:
        normalized = build_default_dataframe()

    options = get_row_options(normalized)
    selected_option = st.selectbox(
        "Selecione o dia para editar",
        options=options,
        key="quick_edit_day",
    )
    selected_index = int(selected_option.split(" | ", maxsplit=1)[0])
    current = normalized.iloc[selected_index]

    with st.form("quick_edit_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            dia = st.selectbox(
                "Dia da semana",
                options=WEEKDAY_OPTIONS,
                index=WEEKDAY_OPTIONS.index(current["dia"])
                if current["dia"] in WEEKDAY_OPTIONS
                else 0,
            )
        with col2:
            data_value = st.date_input("Data", value=parse_iso_date(current["data"]))
        with col3:
            ultima_atualizacao = st.text_input(
                "Última atualização",
                value=current["ultima_atualizacao"] or datetime.now().strftime("%H:%M"),
                help="Formato HH:MM",
            )

        prato_principal = st.text_input("Prato principal", value=current["prato_principal"])
        acompanhamento = st.text_input("Acompanhamento", value=current["acompanhamento"])
        col4, col5 = st.columns(2)
        with col4:
            salada = st.text_input("Salada", value=current["salada"])
        with col5:
            sobremesa = st.text_input("Sobremesa", value=current["sobremesa"])

        aviso = st.text_area(
            "Aviso do dia",
            value=current["aviso"],
            height=100,
        )

        submitted = st.form_submit_button(
            "Aplicar alteração neste dia",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        normalized.loc[selected_index, SHEET_COLUMNS] = {
            "dia": dia,
            "data": data_value.strftime("%Y-%m-%d"),
            "prato_principal": prato_principal.strip(),
            "acompanhamento": acompanhamento.strip(),
            "salada": salada.strip(),
            "sobremesa": sobremesa.strip(),
            "aviso": aviso.strip(),
            "ultima_atualizacao": ultima_atualizacao.strip(),
        }
        set_draft_dataframe(normalized)
        st.success("Alteração aplicada na tela. Agora você pode salvar na planilha.")


def render_complete_editor(dataframe: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Tabela completa</div>
            <div class="panel-subtitle">
                Use este modo para adicionar, remover ou editar várias linhas.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    edited = st.data_editor(
        normalize_dataframe(dataframe),
        key="full_editor",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "dia": st.column_config.SelectboxColumn(
                "Dia",
                options=WEEKDAY_OPTIONS,
                required=True,
                width="small",
            ),
            "data": st.column_config.TextColumn(
                "Data",
                help="Formato YYYY-MM-DD",
                width="medium",
            ),
            "prato_principal": st.column_config.TextColumn(
                "Prato principal",
                width="large",
            ),
            "acompanhamento": st.column_config.TextColumn(
                "Acompanhamento",
                width="large",
            ),
            "salada": st.column_config.TextColumn("Salada", width="medium"),
            "sobremesa": st.column_config.TextColumn("Sobremesa", width="medium"),
            "aviso": st.column_config.TextColumn("Aviso", width="large"),
            "ultima_atualizacao": st.column_config.TextColumn(
                "Última atualização",
                help="Formato HH:MM",
                width="small",
            ),
        },
    )
    set_draft_dataframe(edited)


def render_preview(dataframe: pd.DataFrame) -> None:
    normalized = normalize_dataframe(dataframe).reset_index(drop=True)

    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Prévia do app</div>
            <div class="panel-subtitle">
                Visualize como o cardápio deve aparecer para o usuário final.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if normalized.empty:
        st.warning("Nenhum cardápio cadastrado para pré-visualizar.")
        return

    preview_options = get_row_options(normalized)
    selected_option = st.selectbox(
        "Dia para pré-visualizar",
        options=preview_options,
        key="preview_day",
    )
    selected_index = int(selected_option.split(" | ", maxsplit=1)[0])
    row = normalized.iloc[selected_index]

    chips_html = "".join(
        f'<div class="day-chip {"active" if day == row["dia"] else ""}">{html.escape(day)}</div>'
        for day in WEEKDAY_OPTIONS[:5]
    )

    display_date = html.escape(format_display_date(row["dia"], row["data"]))
    aviso = html.escape(row["aviso"] or "Cardápio sujeito a alterações.")
    ultima = html.escape(row["ultima_atualizacao"] or "--:--")

    st.markdown(
        f"""
        <div class="preview-shell">
            <div style="font-size: 2rem; font-weight: 850; color: #123f18;">Cardápio Semanal</div>
            <div class="soft-caption">Consulte o cardápio da semana</div>
            <div class="day-chip-row">{chips_html}</div>
            <div class="date-banner">{display_date}</div>
            <div class="meal-card">
                <div class="meal-title">Almoço</div>
                <div class="menu-row">
                    <div class="menu-label">Prato principal</div>
                    <div class="menu-value">{html.escape(row["prato_principal"])}</div>
                </div>
                <div class="menu-row">
                    <div class="menu-label">Acompanhamento</div>
                    <div class="menu-value">{html.escape(row["acompanhamento"])}</div>
                </div>
                <div class="menu-row">
                    <div class="menu-label">Salada</div>
                    <div class="menu-value">{html.escape(row["salada"])}</div>
                </div>
                <div class="menu-row">
                    <div class="menu-label">Sobremesa</div>
                    <div class="menu-value">{html.escape(row["sobremesa"])}</div>
                </div>
            </div>
            <div class="notice-card">
                <div class="notice-title">Avisos</div>
                <div>{aviso}</div>
                <div class="soft-caption">Última atualização: {ultima}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_csv_preview(dataframe: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Prévia CSV</div>
            <div class="panel-subtitle">
                Este é o conteúdo que o Flutter pode consumir ao ler a planilha.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.code(normalize_dataframe(dataframe).to_csv(index=False), language="csv")


def render_action_bar(config: AppConfig, dataframe: pd.DataFrame) -> None:
    col1, col2, col3 = st.columns([1.45, 1, 1])

    with col1:
        if st.button("Salvar alterações na planilha", type="primary", use_container_width=True):
            errors = validate_dataframe(dataframe)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    save_menu_dataframe(config, dataframe)
                except Exception as error:  # noqa: BLE001
                    st.error(f"Erro ao salvar: {error}")
                else:
                    st.success("Planilha atualizada com sucesso.")

    with col2:
        if st.button("Recarregar da planilha", use_container_width=True):
            load_menu_dataframe.clear()
            st.session_state.pop("draft_sheet_key", None)
            st.session_state.pop("draft_df", None)
            st.rerun()

    with col3:
        csv_data = normalize_dataframe(dataframe).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Baixar CSV",
            data=csv_data,
            file_name="cardapio.csv",
            mime="text/csv",
            use_container_width=True,
        )


def main() -> None:
    st.set_page_config(
        page_title="Painel do Cardápio",
        page_icon="🥗",
        layout="wide",
    )
    inject_css()
    require_login()

    config = render_sidebar()
    render_header()

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

    initialize_draft(dataframe, config)
    render_metrics(get_draft_dataframe())
    st.write("")
    render_action_bar(config, get_draft_dataframe())
    st.write("")

    tab_quick, tab_table, tab_preview, tab_csv = st.tabs(
        ["Edição rápida", "Tabela completa", "Prévia do app", "CSV"]
    )

    with tab_quick:
        render_quick_edit(get_draft_dataframe())

    with tab_table:
        render_complete_editor(get_draft_dataframe())

    with tab_preview:
        render_preview(get_draft_dataframe())

    with tab_csv:
        render_csv_preview(get_draft_dataframe())


if __name__ == "__main__":
    main()
