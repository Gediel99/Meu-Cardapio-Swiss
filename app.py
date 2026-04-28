from __future__ import annotations

import hmac
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


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state.pop("auth_username", None)
    st.rerun()


def authenticate(username: str, password: str, auth_config: AuthConfig) -> bool:
    username_ok = hmac.compare_digest(username.strip(), auth_config.username)
    password_ok = hmac.compare_digest(password.strip(), auth_config.password)
    return username_ok and password_ok


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
                max-width: 1180px;
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #f6fbf4 0%, #ffffff 100%);
                border-right: 1px solid rgba(46, 125, 50, 0.12);
            }

            .hero-card {
                padding: 1.6rem 1.8rem;
                border-radius: 24px;
                background: linear-gradient(135deg, #f1f8ed 0%, #ffffff 58%, #fff7ec 100%);
                border: 1px solid rgba(46, 125, 50, 0.12);
                box-shadow: 0 18px 45px rgba(27, 94, 32, 0.08);
                margin-bottom: 1.1rem;
            }

            .hero-title {
                font-size: 2.35rem;
                line-height: 1.05;
                font-weight: 800;
                color: #123f18;
                margin: 0;
            }

            .hero-subtitle {
                color: #647067;
                font-size: 1rem;
                margin-top: 0.55rem;
            }

            .sheet-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                padding: 0.45rem 0.75rem;
                border-radius: 999px;
                background: #eaf6e7;
                color: #2e7d32;
                font-weight: 700;
                border: 1px solid rgba(46, 125, 50, 0.18);
                margin-top: 1rem;
                font-size: 0.9rem;
            }

            .metric-card {
                padding: 1rem 1.1rem;
                border-radius: 18px;
                background: #ffffff;
                border: 1px solid rgba(18, 63, 24, 0.10);
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.045);
            }

            .metric-label {
                color: #6b746d;
                font-size: 0.83rem;
                margin-bottom: 0.2rem;
            }

            .metric-value {
                color: #123f18;
                font-size: 1.45rem;
                font-weight: 800;
            }

            .preview-wrapper {
                padding: 1.1rem;
                border-radius: 26px;
                background: linear-gradient(180deg, #f7fbf5 0%, #ffffff 100%);
                border: 1px solid rgba(46, 125, 50, 0.12);
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.055);
            }

            .day-chip-row {
                display: flex;
                gap: 0.55rem;
                flex-wrap: wrap;
                margin: 0.8rem 0 1rem 0;
            }

            .day-chip {
                padding: 0.55rem 0.85rem;
                border-radius: 16px;
                background: #ffffff;
                color: #566058;
                border: 1px solid rgba(0, 0, 0, 0.08);
                font-weight: 700;
            }

            .day-chip.active {
                background: #eaf6e7;
                color: #2e7d32;
                border: 1px solid rgba(46, 125, 50, 0.45);
            }

            .date-banner {
                padding: 0.85rem 1rem;
                border-radius: 18px;
                background: #eef8e9;
                color: #2e7d32;
                font-weight: 800;
                margin-bottom: 1rem;
                border: 1px solid rgba(46, 125, 50, 0.14);
            }

            .meal-card {
                padding: 1.2rem;
                border-radius: 24px;
                background: #ffffff;
                border: 1px solid rgba(0, 0, 0, 0.07);
                box-shadow: 0 12px 32px rgba(0, 0, 0, 0.06);
            }

            .meal-title {
                font-size: 1.65rem;
                color: #e07016;
                font-weight: 850;
                margin-bottom: 0.8rem;
            }

            .menu-row {
                display: grid;
                grid-template-columns: minmax(120px, 190px) 1fr;
                gap: 1rem;
                padding: 0.65rem 0;
                border-bottom: 1px solid rgba(0, 0, 0, 0.075);
            }

            .menu-row:last-child {
                border-bottom: none;
            }

            .menu-label {
                color: #5f6b63;
                font-weight: 650;
            }

            .menu-value {
                color: #181d19;
                font-weight: 750;
            }

            .notice-card {
                padding: 1rem 1.1rem;
                margin-top: 1rem;
                border-radius: 20px;
                background: #fff8ea;
                border: 1px solid rgba(224, 112, 22, 0.18);
            }

            .notice-title {
                color: #d36313;
                font-weight: 850;
                font-size: 1.15rem;
                margin-bottom: 0.25rem;
            }

            .soft-caption {
                color: #6c746e;
                font-size: 0.9rem;
            }

            .section-card {
                padding: 1.15rem;
                border-radius: 22px;
                background: #ffffff;
                border: 1px solid rgba(18, 63, 24, 0.10);
                box-shadow: 0 10px 28px rgba(0, 0, 0, 0.045);
                margin-bottom: 1rem;
            }

            div[data-testid="stButton"] > button {
                border-radius: 14px;
                font-weight: 750;
            }

            div[data-testid="stForm"] {
                border-radius: 20px;
                border: 1px solid rgba(18, 63, 24, 0.10);
                padding: 1rem;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.035);
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

    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown(
            """
            <div class="hero-card">
                <p class="hero-title">🥗 Acesso administrativo</p>
                <div class="hero-subtitle">Entre para editar o cardápio semanal.</div>
                <div class="sheet-pill">🔒 Painel protegido</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
    return normalize_dataframe(dataframe)


def normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    for column in SHEET_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    normalized = normalized[SHEET_COLUMNS].fillna("")
    normalized["dia"] = normalized["dia"].astype(str).str.strip()
    normalized["data"] = normalized["data"].astype(str).str.strip()
    normalized["ultima_atualizacao"] = normalized["ultima_atualizacao"].astype(str).str.strip()
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


def render_sidebar() -> AppConfig:
    with st.sidebar:
        st.markdown("## ⚙️ Configuração")
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
            <p class="hero-title">🥗 Painel do Cardápio</p>
            <div class="hero-subtitle">
                Cadastre e atualize o almoço da semana sem abrir a planilha manualmente.
            </div>
            <div class="sheet-pill">📄 Google Sheets conectado</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(dataframe: pd.DataFrame) -> None:
    normalized = normalize_dataframe(dataframe)
    total_days = len(normalized[normalized["data"].astype(str).str.strip() != ""])
    last_update_values = [
        value for value in normalized["ultima_atualizacao"].astype(str).tolist() if value.strip()
    ]
    last_update = last_update_values[-1] if last_update_values else "-"
    filled_main_dishes = normalized["prato_principal"].astype(str).str.strip().ne("").sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Dias cadastrados</div>
                <div class="metric-value">{total_days}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Pratos principais</div>
                <div class="metric-value">{filled_main_dishes}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Última atualização</div>
                <div class="metric-value">{last_update}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_row_options(dataframe: pd.DataFrame) -> list[str]:
    options: list[str] = []
    for index, row in normalize_dataframe(dataframe).reset_index(drop=True).iterrows():
        weekday = str(row["dia"]).strip() or "Dia"
        iso_date = str(row["data"]).strip() or "sem-data"
        main_dish = str(row["prato_principal"]).strip() or "sem prato"
        options.append(f"{index} | {weekday} | {iso_date} | {main_dish}")
    return options


def render_quick_edit(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_dataframe(dataframe).reset_index(drop=True)

    st.markdown("### ✏️ Edição rápida por dia")
    st.caption("Use esta área para alterar um dia específico sem mexer na tabela inteira.")

    if normalized.empty:
        normalized = build_default_dataframe()

    options = get_row_options(normalized)
    selected_option = st.selectbox("Selecione o dia para editar", options=options)
    selected_index = int(selected_option.split(" | ", maxsplit=1)[0])
    current = normalized.iloc[selected_index]

    with st.form("quick_edit_form"):
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            dia = st.selectbox(
                "Dia da semana",
                options=WEEKDAY_OPTIONS,
                index=WEEKDAY_OPTIONS.index(current["dia"]) if current["dia"] in WEEKDAY_OPTIONS else 0,
            )
        with col2:
            data_value = st.date_input("Data", value=parse_iso_date(current["data"]))
        with col3:
            ultima_atualizacao = st.text_input(
                "Última atualização",
                value=str(current["ultima_atualizacao"] or datetime.now().strftime("%H:%M")),
                help="Formato HH:MM",
            )

        prato_principal = st.text_input(
            "Prato principal",
            value=str(current["prato_principal"]),
            placeholder="Ex.: Frango grelhado",
        )
        acompanhamento = st.text_input(
            "Acompanhamento",
            value=str(current["acompanhamento"]),
            placeholder="Ex.: Arroz, feijão e purê",
        )
        col4, col5 = st.columns(2)
        with col4:
            salada = st.text_input("Salada", value=str(current["salada"]))
        with col5:
            sobremesa = st.text_input("Sobremesa", value=str(current["sobremesa"]))

        aviso = st.text_area(
            "Aviso do dia",
            value=str(current["aviso"]),
            placeholder="Ex.: Cardápio sujeito a alterações.",
            height=90,
        )

        submitted = st.form_submit_button("Aplicar alteração neste dia", type="primary", use_container_width=True)

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
        st.success("Alteração aplicada na tela. Clique em Salvar na planilha para gravar no Google Sheets.")

    return normalized


def render_complete_editor(dataframe: pd.DataFrame) -> pd.DataFrame:
    st.markdown("### 🧾 Tabela completa")
    st.caption("Use este modo para adicionar/remover linhas ou fazer ajustes em massa.")

    edited = st.data_editor(
        normalize_dataframe(dataframe),
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
            "data": st.column_config.TextColumn("Data", help="Formato YYYY-MM-DD", width="medium"),
            "prato_principal": st.column_config.TextColumn("Prato principal", width="large"),
            "acompanhamento": st.column_config.TextColumn("Acompanhamento", width="large"),
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
    return normalize_dataframe(edited)


def render_preview(dataframe: pd.DataFrame) -> None:
    normalized = normalize_dataframe(dataframe).reset_index(drop=True)

    st.markdown("### 👀 Prévia visual")
    st.caption("Veja como o cardápio deve aparecer para o usuário no app.")

    if normalized.empty:
        st.warning("Nenhum cardápio cadastrado para pré-visualizar.")
        return

    preview_options = get_row_options(normalized)
    selected_option = st.selectbox("Dia para pré-visualizar", options=preview_options, key="preview_day")
    selected_index = int(selected_option.split(" | ", maxsplit=1)[0])
    row = normalized.iloc[selected_index]

    chips_html = "".join(
        f'<div class="day-chip {"active" if day == row["dia"] else ""}">📅 {day}</div>'
        for day in WEEKDAY_OPTIONS[:5]
    )

    display_date = format_display_date(str(row["dia"]), str(row["data"]))
    aviso = str(row["aviso"]).strip() or "Cardápio sujeito a alterações."
    ultima = str(row["ultima_atualizacao"]).strip() or "--:--"

    st.markdown(
        f"""
        <div class="preview-wrapper">
            <div style="font-size: 2rem; font-weight: 850; color: #123f18;">Cardápio Semanal</div>
            <div class="soft-caption">Consulte o cardápio da semana</div>
            <div class="sheet-pill">📄 Atualizado via Google Sheets</div>
            <div class="day-chip-row">{chips_html}</div>
            <div class="date-banner">📅 {display_date}</div>
            <div class="meal-card">
                <div class="meal-title">🍽️ Almoço</div>
                <div class="menu-row">
                    <div class="menu-label">Prato principal</div>
                    <div class="menu-value">{row['prato_principal']}</div>
                </div>
                <div class="menu-row">
                    <div class="menu-label">Acompanhamento</div>
                    <div class="menu-value">{row['acompanhamento']}</div>
                </div>
                <div class="menu-row">
                    <div class="menu-label">Salada</div>
                    <div class="menu-value">{row['salada']}</div>
                </div>
                <div class="menu-row">
                    <div class="menu-label">Sobremesa</div>
                    <div class="menu-value">{row['sobremesa']}</div>
                </div>
            </div>
            <div class="notice-card">
                <div class="notice-title">🔔 Avisos</div>
                <div>{aviso}</div>
                <div class="soft-caption">🕒 Última atualização: {ultima}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def save_actions(config: AppConfig, dataframe: pd.DataFrame) -> None:
    st.divider()
    col1, col2, col3 = st.columns([1.4, 1, 1])

    with col1:
        if st.button("💾 Salvar alterações na planilha", type="primary", use_container_width=True):
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
                    st.balloons()

    with col2:
        if st.button("🔄 Recarregar", use_container_width=True):
            load_menu_dataframe.clear()
            st.rerun()

    with col3:
        csv_data = normalize_dataframe(dataframe).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Baixar CSV",
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

    dataframe = normalize_dataframe(dataframe)
    render_metrics(dataframe)
    st.write("")

    tab_quick, tab_table, tab_preview, tab_csv = st.tabs(
        ["✏️ Edição rápida", "🧾 Tabela completa", "👀 Prévia do app", "📤 CSV"]
    )

    working_dataframe = dataframe

    with tab_quick:
        working_dataframe = render_quick_edit(working_dataframe)
        save_actions(config, working_dataframe)

    with tab_table:
        table_dataframe = render_complete_editor(working_dataframe)
        save_actions(config, table_dataframe)

    with tab_preview:
        render_preview(working_dataframe)

    with tab_csv:
        st.markdown("### 📤 Prévia CSV")
        st.caption("Este é o conteúdo que será usado pelo Flutter ao ler a planilha como CSV.")
        st.code(normalize_dataframe(working_dataframe).to_csv(index=False), language="csv")


if __name__ == "__main__":
    main()
