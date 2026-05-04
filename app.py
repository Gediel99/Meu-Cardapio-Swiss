from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

APP_NAME = "My Cardápio Swiss"
RELEASES_DIR = Path(__file__).resolve().parent / "releases"
DEFAULT_SHEET_ID = "1lJznRnmCxV6ulrVsMBbnVi1qD-FCOapLfh3Hv7fxNoE"
DEFAULT_WORKSHEET = "cardapio"
DEFAULT_USERS_WORKSHEET = "usuarios"
DEFAULT_TEMPLATES_WORKSHEET = "modelos_refeicao"

BASE_SHEET_COLUMNS = [
    "dia",
    "data",
    "prato_principal",
    "acompanhamento",
    "salada",
    "sobremesa",
    "aviso",
    "ultima_atualizacao",
]
USER_COLUMNS = ["username", "password_hash", "role", "active", "created_at"]
TEMPLATE_COLUMNS = [
    "nome_modelo",
    "prato_principal",
    "acompanhamento",
    "salada",
    "sobremesa",
    "aviso",
]
WEEK_TEMPLATE = [
    ("Seg", 0),
    ("Ter", 1),
    ("Qua", 2),
    ("Qui", 3),
    ("Sex", 4),
]
WEEKDAY_OPTIONS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
WEEKDAY_FULL_NAMES = {
    "Seg": "Segunda-feira",
    "Ter": "Terça-feira",
    "Qua": "Quarta-feira",
    "Qui": "Quinta-feira",
    "Sex": "Sexta-feira",
    "Sab": "Sábado",
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
class UserAccount:
    username: str
    password: str
    role: str

    @property
    def is_configured(self) -> bool:
        return bool(self.username.strip() and self.password.strip())


@dataclass(frozen=True)
class AuthConfig:
    accounts: tuple[UserAccount, ...]

    @property
    def is_configured(self) -> bool:
        return any(account.is_configured for account in self.accounts)


@dataclass(frozen=True)
class MealTemplate:
    name: str
    main_dish: str
    side_dish: str
    salad: str
    dessert: str
    notice: str


def get_secret_value(key: str, default: str = "") -> str:
    if key in st.secrets:
        return str(st.secrets[key])
    return os.getenv(key, default)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def format_file_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{int(num_bytes)} B"


def get_release_files() -> list[Path]:
    if not RELEASES_DIR.exists():
        return []

    return sorted(
        [
            path
            for path in RELEASES_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in {".apk", ".aab"}
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def get_release_label(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    name = file_path.name.lower()
    if suffix == ".apk":
        return "Android APK"
    if suffix == ".aab":
        return "Android App Bundle"
    if suffix == ".zip" and "windows" in name:
        return "Windows ZIP"
    if suffix == ".exe":
        return "Windows EXE"
    return file_path.suffix.replace(".", "").upper() or "Arquivo"


def is_admin() -> bool:
    return st.session_state.get("auth_role") == "admin"


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state.pop("auth_username", None)
    st.session_state.pop("auth_role", None)
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
                max-width: 1180px;
                padding-top: 2.2rem;
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
                font-size: 2.15rem;
                line-height: 1.06;
                font-weight: 850;
            }

            .hero-subtitle {
                margin-top: 0.45rem;
                color: #647067;
                font-size: 1rem;
                max-width: 42rem;
            }

            .hero-logo {
                min-width: 150px;
                text-align: right;
                color: #123f18;
                font-weight: 800;
                font-size: 1.05rem;
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
                width: 100%;
                max-width: 100%;
                box-sizing: border-box;
                overflow: hidden;
            }

            .public-shell {
                margin-bottom: 1.1rem;
            }

            .public-kicker {
                display: inline-flex;
                align-items: center;
                padding: 0.4rem 0.72rem;
                border-radius: 999px;
                background: #eaf6e7;
                border: 1px solid rgba(46, 125, 50, 0.16);
                color: #2e7d32;
                font-size: 0.84rem;
                font-weight: 800;
                margin-bottom: 0.85rem;
            }

            .public-title {
                margin: 0;
                color: #123f18;
                font-size: 2.25rem;
                line-height: 1.02;
                font-weight: 900;
            }

            .public-subtitle {
                margin: 0.6rem 0 0 0;
                color: #657067;
                font-size: 1rem;
                max-width: 34rem;
            }

            .public-topbar {
                display: flex;
                justify-content: flex-end;
                margin-bottom: 0.35rem;
            }

            .login-card {
                padding: 1.1rem;
                border-radius: 24px;
                background: rgba(255, 255, 255, 0.94);
                border: 1px solid rgba(18, 63, 24, 0.08);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
            }

            .login-title {
                color: #123f18;
                font-size: 1.2rem;
                font-weight: 850;
                margin-bottom: 0.2rem;
            }

            .login-subtitle {
                color: #657067;
                font-size: 0.94rem;
                margin-bottom: 0.9rem;
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

                .public-title {
                    font-size: 1.95rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _read_account(section: Any, role: str) -> UserAccount:
    if isinstance(section, dict):
        username = str(section.get("username", "")).strip()
        password = str(section.get("password", "")).strip()
        return UserAccount(username=username, password=password, role=role)
    return UserAccount(username="", password="", role=role)


def get_auth_config() -> AuthConfig:
    auth_section = st.secrets.get("auth", {}) if hasattr(st, "secrets") else {}

    admin_account = _read_account(auth_section.get("admin", {}), "admin")
    user_account = _read_account(auth_section.get("user", {}), "user")

    if not admin_account.is_configured:
        admin_account = UserAccount(
            username=(
                get_secret_value("ADMIN_USERNAME")
                or str(auth_section.get("username", "")).strip()
            ),
            password=(
                get_secret_value("ADMIN_PASSWORD")
                or str(auth_section.get("password", "")).strip()
            ),
            role="admin",
        )

    if not user_account.is_configured:
        user_account = UserAccount(
            username=(
                get_secret_value("USER_USERNAME")
                or get_secret_value("COMMON_USERNAME")
            ),
            password=(
                get_secret_value("USER_PASSWORD")
                or get_secret_value("COMMON_PASSWORD")
            ),
            role="user",
        )

    return AuthConfig(accounts=(admin_account, user_account))


def authenticate(
    username: str,
    password: str,
    auth_config: AuthConfig,
) -> UserAccount | None:
    typed_username = username.strip()
    typed_password = password.strip()

    for account in auth_config.accounts:
        if not account.is_configured:
            continue

        username_ok = hmac.compare_digest(typed_username, account.username)
        password_ok = hmac.compare_digest(typed_password, account.password)
        if username_ok and password_ok:
            return account

    try:
        for account in load_registered_users(DEFAULT_SHEET_ID):
            username_ok = hmac.compare_digest(typed_username, account.username)
            password_ok = hmac.compare_digest(
                hash_password(typed_password),
                account.password,
            )
            if username_ok and password_ok:
                return account
    except Exception:
        pass

    return None


def get_public_menu_dataframe() -> pd.DataFrame:
    try:
        dataframe = load_menu_dataframe(DEFAULT_SHEET_ID, DEFAULT_WORKSHEET)
    except Exception:
        return build_default_dataframe()

    if dataframe.empty:
        return build_default_dataframe()
    return dataframe


def render_login_gate(public_dataframe: pd.DataFrame) -> None:
    auth_config = get_auth_config()

    if st.session_state.get("authenticated") is True:
        return

    render_public_home(public_dataframe, auth_config)
    st.stop()


def require_login() -> None:
    auth_config = get_auth_config()

    if not auth_config.is_configured:
        st.error("Login administrativo não configurado.")
        st.info(
            "Configure usuários e senhas nos Secrets do Streamlit Cloud "
            "ou no arquivo .streamlit/secrets.toml local."
        )
        st.stop()

    if st.session_state.get("authenticated") is True:
        return

    _, center, _ = st.columns([1, 1.1, 1])
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
            account = authenticate(username, password, auth_config)
            if account is not None:
                st.session_state["authenticated"] = True
                st.session_state["auth_username"] = account.username
                st.session_state["auth_role"] = account.role
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


def normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    for column in BASE_SHEET_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    ordered_columns = BASE_SHEET_COLUMNS + [
        column for column in normalized.columns if column not in BASE_SHEET_COLUMNS
    ]
    normalized = normalized[ordered_columns].fillna("")

    for column in ordered_columns:
        normalized[column] = normalized[column].astype(str).str.strip()

    return normalized


def get_extra_columns(dataframe: pd.DataFrame) -> list[str]:
    normalized = normalize_dataframe(dataframe)
    return [column for column in normalized.columns if column not in BASE_SHEET_COLUMNS]


@st.cache_data(show_spinner=False, ttl=30)
def load_menu_dataframe(sheet_id: str, worksheet_name: str) -> pd.DataFrame:
    worksheet = get_gspread_client().open_by_key(sheet_id).worksheet(worksheet_name)
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=BASE_SHEET_COLUMNS)
    return normalize_dataframe(pd.DataFrame(records))


@st.cache_data(show_spinner=False, ttl=30)
def load_registered_users(sheet_id: str) -> tuple[UserAccount, ...]:
    try:
        worksheet = get_gspread_client().open_by_key(sheet_id).worksheet(
            DEFAULT_USERS_WORKSHEET
        )
    except gspread.WorksheetNotFound:
        return ()

    records = worksheet.get_all_records()
    accounts: list[UserAccount] = []
    for row in records:
        username = str(row.get("username", "")).strip()
        password_hash = str(row.get("password_hash", "")).strip()
        role = str(row.get("role", "user")).strip().lower() or "user"
        active = str(row.get("active", "TRUE")).strip().lower()

        if not username or not password_hash or active in {"false", "0", "no"}:
            continue
        if role not in {"admin", "user"}:
            role = "user"

        accounts.append(UserAccount(username=username, password=password_hash, role=role))

    return tuple(accounts)


@st.cache_data(show_spinner=False, ttl=30)
def load_meal_templates(sheet_id: str) -> tuple[MealTemplate, ...]:
    try:
        worksheet = get_gspread_client().open_by_key(sheet_id).worksheet(
            DEFAULT_TEMPLATES_WORKSHEET
        )
    except gspread.WorksheetNotFound:
        return ()

    records = worksheet.get_all_records()
    templates: list[MealTemplate] = []
    for row in records:
        template_name = str(row.get("nome_modelo", "")).strip()
        if not template_name:
            continue
        templates.append(
            MealTemplate(
                name=template_name,
                main_dish=str(row.get("prato_principal", "")).strip(),
                side_dish=str(row.get("acompanhamento", "")).strip(),
                salad=str(row.get("salada", "")).strip(),
                dessert=str(row.get("sobremesa", "")).strip(),
                notice=str(row.get("aviso", "")).strip(),
            )
        )
    return tuple(templates)


def ensure_users_worksheet(sheet_id: str) -> gspread.Worksheet:
    spreadsheet = get_gspread_client().open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(DEFAULT_USERS_WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=DEFAULT_USERS_WORKSHEET,
            rows=50,
            cols=len(USER_COLUMNS),
        )
        worksheet.update("A1:E1", [USER_COLUMNS])
        return worksheet

    if worksheet.row_values(1)[: len(USER_COLUMNS)] != USER_COLUMNS:
        worksheet.update("A1:E1", [USER_COLUMNS])
    return worksheet


def ensure_templates_worksheet(sheet_id: str) -> gspread.Worksheet:
    spreadsheet = get_gspread_client().open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(DEFAULT_TEMPLATES_WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=DEFAULT_TEMPLATES_WORKSHEET,
            rows=50,
            cols=len(TEMPLATE_COLUMNS),
        )
        worksheet.update("A1:F1", [TEMPLATE_COLUMNS])
        return worksheet

    if worksheet.row_values(1)[: len(TEMPLATE_COLUMNS)] != TEMPLATE_COLUMNS:
        worksheet.update("A1:F1", [TEMPLATE_COLUMNS])
    return worksheet


def save_menu_dataframe(config: AppConfig, dataframe: pd.DataFrame) -> None:
    worksheet = get_gspread_client().open_by_key(config.sheet_id).worksheet(
        config.worksheet_name
    )
    normalized = normalize_dataframe(dataframe)
    columns = normalized.columns.tolist()
    rows = [columns] + normalized.astype(str).values.tolist()
    worksheet.clear()
    end_column_letter = chr(64 + min(len(columns), 26))
    worksheet.update(f"A1:{end_column_letter}1", [columns])
    worksheet.update("A1", rows, value_input_option="USER_ENTERED")
    load_menu_dataframe.clear()


def save_registered_user(sheet_id: str, username: str, password: str, role: str) -> None:
    worksheet = ensure_users_worksheet(sheet_id)
    username = username.strip()
    password_hash = hash_password(password.strip())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    records = worksheet.get_all_records()
    existing_row_number: int | None = None

    for index, row in enumerate(records, start=2):
        if str(row.get("username", "")).strip().lower() == username.lower():
            existing_row_number = index
            break

    values = [[username, password_hash, role.strip().lower(), "TRUE", timestamp]]
    if existing_row_number is not None:
        worksheet.update(f"A{existing_row_number}:E{existing_row_number}", values)
    else:
        worksheet.append_rows(values, value_input_option="USER_ENTERED")

    load_registered_users.clear()


def update_registered_user_role(sheet_id: str, username: str, role: str) -> None:
    worksheet = ensure_users_worksheet(sheet_id)
    records = worksheet.get_all_records()

    for index, row in enumerate(records, start=2):
        if str(row.get("username", "")).strip().lower() == username.strip().lower():
            worksheet.update(f"C{index}:D{index}", [[role.strip().lower(), "TRUE"]])
            load_registered_users.clear()
            return

    raise ValueError("Usuário não encontrado para alteração de perfil.")


def save_meal_template(sheet_id: str, template: MealTemplate) -> None:
    worksheet = ensure_templates_worksheet(sheet_id)
    records = worksheet.get_all_records()
    existing_row_number: int | None = None

    for index, row in enumerate(records, start=2):
        if str(row.get("nome_modelo", "")).strip().lower() == template.name.lower():
            existing_row_number = index
            break

    values = [[
        template.name,
        template.main_dish,
        template.side_dish,
        template.salad,
        template.dessert,
        template.notice,
    ]]

    if existing_row_number is not None:
        worksheet.update(f"A{existing_row_number}:F{existing_row_number}", values)
    else:
        worksheet.append_rows(values, value_input_option="USER_ENTERED")

    load_meal_templates.clear()


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
        columns=BASE_SHEET_COLUMNS,
    )


def get_next_monday(reference_date: date) -> date:
    days_until_next_monday = (7 - reference_date.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7
    return reference_date + timedelta(days=days_until_next_monday)


def build_next_week_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_dataframe(dataframe).reset_index(drop=True)
    valid_dates = [
        parse_iso_date(value)
        for value in normalized["data"].tolist()
        if str(value).strip()
    ]
    base_date = max(valid_dates) if valid_dates else date.today()
    next_monday = get_next_monday(base_date)
    extra_columns = get_extra_columns(normalized)
    notice = "Cardápio sujeito a alterações."

    if not normalized.empty:
        first_notice = str(normalized.iloc[0]["aviso"]).strip()
        if first_notice:
            notice = first_notice

    rows: list[dict[str, str]] = []
    for weekday_label, day_offset in WEEK_TEMPLATE:
        current_date = next_monday + timedelta(days=day_offset)
        row = {
            "dia": weekday_label,
            "data": current_date.strftime("%Y-%m-%d"),
            "prato_principal": "",
            "acompanhamento": "",
            "salada": "",
            "sobremesa": "",
            "aviso": notice,
            "ultima_atualizacao": "",
        }
        for column in extra_columns:
            row[column] = ""
        rows.append(row)

    return normalize_dataframe(pd.DataFrame(rows))


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


def format_short_date(iso_date: str) -> str:
    parsed = parse_iso_date(iso_date)
    return parsed.strftime("%d/%m")


def get_row_indices(dataframe: pd.DataFrame) -> list[int]:
    return list(range(len(normalize_dataframe(dataframe).reset_index(drop=True))))


def get_row_display_label(dataframe: pd.DataFrame, index: int) -> str:
    normalized = normalize_dataframe(dataframe).reset_index(drop=True)
    row = normalized.iloc[index]
    weekday_short = row["dia"] or "Dia"
    weekday_full = WEEKDAY_FULL_NAMES.get(weekday_short, weekday_short)
    short_date = format_short_date(row["data"])
    main_dish = row["prato_principal"] or "Sem prato definido"
    return f"{weekday_full} • {short_date} • {main_dish}"


def render_day_button_picker(
    dataframe: pd.DataFrame,
    *,
    state_key: str,
    caption: str,
) -> int:
    normalized = normalize_dataframe(dataframe).reset_index(drop=True)
    options = get_row_indices(normalized)

    if not options:
        return 0

    current_value = st.session_state.get(state_key)
    if current_value not in options:
        st.session_state[state_key] = options[0]

    selected_index = st.segmented_control(
        caption,
        options=options,
        default=int(st.session_state.get(state_key, options[0])),
        format_func=lambda index: str(normalized.iloc[index]["dia"]).strip()
        or f"Dia {index + 1}",
        key=state_key,
        selection_mode="single",
    )

    if selected_index is None:
        selected_index = options[0]

    selected_index = int(selected_index)
    st.caption(get_row_display_label(normalized, selected_index))
    return selected_index


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


def add_extra_column_to_draft(dataframe: pd.DataFrame, column_name: str) -> pd.DataFrame:
    normalized = normalize_dataframe(dataframe).copy()
    safe_column_name = column_name.strip()

    if not safe_column_name:
        raise ValueError("Informe um nome de campo.")
    if safe_column_name in normalized.columns:
        raise ValueError("Esse campo já existe na planilha.")

    normalized[safe_column_name] = ""
    return normalize_dataframe(normalized)


def apply_template_to_row(
    dataframe: pd.DataFrame,
    row_index: int,
    template_name: str,
    templates: tuple[MealTemplate, ...],
) -> pd.DataFrame:
    selected_template = next(
        (template for template in templates if template.name == template_name),
        None,
    )
    if selected_template is None:
        raise ValueError("Modelo não encontrado.")

    normalized = normalize_dataframe(dataframe).reset_index(drop=True)
    normalized.loc[row_index, "prato_principal"] = selected_template.main_dish
    normalized.loc[row_index, "acompanhamento"] = selected_template.side_dish
    normalized.loc[row_index, "salada"] = selected_template.salad
    normalized.loc[row_index, "sobremesa"] = selected_template.dessert
    if selected_template.notice:
        normalized.loc[row_index, "aviso"] = selected_template.notice
    return normalize_dataframe(normalized)


def render_sidebar() -> AppConfig:
    with st.sidebar:
        if is_admin():
            st.markdown("## Configuração")
            sheet_id = st.text_input("ID da planilha", value=DEFAULT_SHEET_ID)
            worksheet_name = st.text_input("Nome da aba", value=DEFAULT_WORKSHEET)
            st.info("Compartilhe a planilha com o e-mail do service account como Editor.")
        else:
            st.markdown("## Acesso")
            sheet_id = DEFAULT_SHEET_ID
            worksheet_name = DEFAULT_WORKSHEET
            st.info("Você está no modo de edição rápida do cardápio.")

        st.divider()
        logged_user = st.session_state.get("auth_username", "administrador")
        role_label = "Administrador" if is_admin() else "Usuário comum"
        st.caption(f"Logado como: **{logged_user}**")
        st.caption(f"Perfil: **{role_label}**")
        st.button("Sair", use_container_width=True, on_click=logout)

    return AppConfig(sheet_id=sheet_id.strip(), worksheet_name=worksheet_name.strip())


def render_header() -> None:
    role_hint = (
        "Controle completo da planilha e do painel."
        if is_admin()
        else "Edição rápida liberada para atualização do cardápio."
    )
    st.markdown(
        f"""
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
            <div class="sheet-pill">{html.escape(role_hint)}</div>
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


def render_user_management(sheet_id: str) -> None:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Cadastro de usuários</div>
            <div class="panel-subtitle">
                Crie acessos e promova perfis quando for necessário.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Usuário do funcionário")
        with col2:
            password = st.text_input("Senha", type="password")
            password_confirm = st.text_input("Confirmar senha", type="password")

        submitted = st.form_submit_button(
            "Cadastrar usuário",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        username = username.strip()
        password = password.strip()
        password_confirm = password_confirm.strip()

        if not username:
            st.error("Informe um nome de usuário.")
        elif len(password) < 4:
            st.error("A senha deve ter pelo menos 4 caracteres.")
        elif password != password_confirm:
            st.error("A confirmação de senha não confere.")
        else:
            try:
                save_registered_user(sheet_id, username, password, "user")
            except Exception as error:  # noqa: BLE001
                st.error(f"Erro ao cadastrar usuário: {error}")
            else:
                st.success("Usuário salvo com sucesso como Usuário comum.")

    accounts = load_registered_users(sheet_id)
    if not accounts:
        st.info("Nenhum usuário cadastrado ainda na aba 'usuarios'.")
        return

    users_df = pd.DataFrame(
        [{"username": account.username, "role": account.role} for account in accounts]
    )
    users_df["role"] = users_df["role"].map(
        {"admin": "Administrador", "user": "Usuário comum"}
    )
    st.dataframe(users_df, use_container_width=True, hide_index=True)

    st.markdown("### Alterar perfil")
    manageable_users = [account.username for account in accounts]
    with st.form("change_role_form"):
        col1, col2 = st.columns(2)
        with col1:
            selected_user = st.selectbox("Usuário cadastrado", options=manageable_users)
        with col2:
            new_role = st.selectbox(
                "Novo perfil",
                options=["user", "admin"],
                format_func=lambda value: "Usuário comum" if value == "user" else "Administrador",
            )

        submitted_role = st.form_submit_button(
            "Atualizar perfil",
            use_container_width=True,
        )

    if submitted_role:
        try:
            update_registered_user_role(sheet_id, selected_user, new_role)
        except Exception as error:  # noqa: BLE001
            st.error(f"Erro ao atualizar perfil: {error}")
        else:
            st.success("Perfil atualizado com sucesso.")


def render_template_management(sheet_id: str) -> None:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Modelos de refeição</div>
            <div class="panel-subtitle">
                Cadastre pratos que vocês fazem sempre para puxar tudo mais rápido depois.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("template_form"):
        template_name = st.text_input("Nome do modelo", placeholder="Ex.: Strogonoff")
        main_dish = st.text_input("Prato principal")
        side_dish = st.text_input("Acompanhamento")
        col1, col2 = st.columns(2)
        with col1:
            salad = st.text_input("Salada")
        with col2:
            dessert = st.text_input("Sobremesa")
        notice = st.text_area("Aviso padrão", value="Cardápio sujeito a alterações.", height=90)

        submitted = st.form_submit_button(
            "Salvar modelo",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not template_name.strip():
            st.error("Informe o nome do modelo.")
        else:
            try:
                save_meal_template(
                    sheet_id,
                    MealTemplate(
                        name=template_name.strip(),
                        main_dish=main_dish.strip(),
                        side_dish=side_dish.strip(),
                        salad=salad.strip(),
                        dessert=dessert.strip(),
                        notice=notice.strip(),
                    ),
                )
            except Exception as error:  # noqa: BLE001
                st.error(f"Erro ao salvar modelo: {error}")
            else:
                st.success("Modelo salvo com sucesso.")

    templates = load_meal_templates(sheet_id)
    if templates:
        templates_df = pd.DataFrame(
            [
                {
                    "Modelo": template.name,
                    "Prato principal": template.main_dish,
                    "Acompanhamento": template.side_dish,
                    "Salada": template.salad,
                    "Sobremesa": template.dessert,
                }
                for template in templates
            ]
        )
        st.dataframe(templates_df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum modelo cadastrado ainda.")

    st.markdown("### Criar campo extra na planilha")
    st.caption("Use isso quando precisar guardar uma informação nova além dos campos padrão.")
    with st.form("extra_column_form"):
        column_name = st.text_input(
            "Nome do novo campo",
            placeholder="Ex.: bebida, molho, observacao_chef",
        )
        submitted_column = st.form_submit_button("Adicionar campo", use_container_width=True)

    if submitted_column:
        try:
            updated = add_extra_column_to_draft(get_draft_dataframe(), column_name)
        except Exception as error:  # noqa: BLE001
            st.error(str(error))
        else:
            set_draft_dataframe(updated)
            st.success(
                "Campo extra adicionado na tela. Salve a planilha para gravar essa nova coluna."
            )


def render_quick_edit(dataframe: pd.DataFrame, sheet_id: str) -> None:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Edição rápida por dia</div>
            <div class="panel-subtitle">
                Edite um dia específico ou puxe um modelo pronto para acelerar o cadastro.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    normalized = normalize_dataframe(dataframe).reset_index(drop=True)
    if normalized.empty:
        normalized = build_default_dataframe()

    selected_index = render_day_button_picker(
        normalized,
        state_key="quick_edit_day_button",
        caption="Selecione o dia para editar",
    )

    templates = load_meal_templates(sheet_id)
    if templates:
        template_names = [template.name for template in templates]
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_template = st.selectbox(
                "Modelo de refeição",
                options=template_names,
                index=None,
                placeholder="Selecione um modelo salvo",
                key="quick_edit_template",
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("Aplicar modelo", use_container_width=True):
                if selected_template:
                    updated = apply_template_to_row(
                        normalized,
                        selected_index,
                        selected_template,
                        templates,
                    )
                    set_draft_dataframe(updated)
                    st.success("Modelo aplicado ao dia selecionado.")
                    st.rerun()
                else:
                    st.warning("Selecione um modelo antes de aplicar.")

    current = normalize_dataframe(get_draft_dataframe()).reset_index(drop=True).iloc[selected_index]

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
            data_value = st.date_input(
                "Data",
                value=parse_iso_date(current["data"]),
                format="DD/MM/YYYY",
            )
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

        aviso = st.text_area("Aviso do dia", value=current["aviso"], height=100)

        submitted = st.form_submit_button(
            "Aplicar alteração neste dia",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        working = normalize_dataframe(get_draft_dataframe()).reset_index(drop=True)
        working.loc[selected_index, BASE_SHEET_COLUMNS] = {
            "dia": dia,
            "data": data_value.strftime("%Y-%m-%d"),
            "prato_principal": prato_principal.strip(),
            "acompanhamento": acompanhamento.strip(),
            "salada": salada.strip(),
            "sobremesa": sobremesa.strip(),
            "aviso": aviso.strip(),
            "ultima_atualizacao": ultima_atualizacao.strip(),
        }
        set_draft_dataframe(working)
        st.success("Alteração aplicada na tela. Agora você pode salvar na planilha.")


def render_complete_editor(dataframe: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="panel-card">
            <div class="panel-title">Tabela completa</div>
            <div class="panel-subtitle">
                Use este modo para editar em massa e também preencher campos extras.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    normalized = normalize_dataframe(dataframe)
    column_config: dict[str, Any] = {
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
    }

    for extra_column in get_extra_columns(normalized):
        column_config[extra_column] = st.column_config.TextColumn(extra_column, width="medium")

    edited = st.data_editor(
        normalized,
        key="full_editor",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
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

    preview_options = get_row_indices(normalized)
    selected_index = st.selectbox(
        "Dia para pré-visualizar",
        options=preview_options,
        key="preview_day",
        format_func=lambda index: get_row_display_label(normalized, index),
    )
    row = normalized.iloc[selected_index]

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


def render_app_preview(
    dataframe: pd.DataFrame,
    *,
    selectbox_key: str = "preview_day",
    selectbox_label: str = "Dia para pré-visualizar",
    show_panel: bool = True,
) -> None:
    normalized = normalize_dataframe(dataframe).reset_index(drop=True)

    if show_panel:
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

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="soft-caption" style="margin-top: 0.3rem; margin-bottom: 0.9rem;">
                Consulte o almoço da semana
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_index = render_day_button_picker(
            normalized,
            state_key=selectbox_key,
            caption=selectbox_label,
        )
        row = normalized.iloc[selected_index]

        display_date = html.escape(format_display_date(row["dia"], row["data"]))
        aviso = html.escape(row["aviso"] or "Cardápio sujeito a alterações.")
        ultima = html.escape(row["ultima_atualizacao"] or "--:--")

        st.markdown(
            f"""
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
            """,
            unsafe_allow_html=True,
        )


def render_downloads_section() -> None:
    files = get_release_files()

    st.markdown(
        """
        <div class="panel-card" style="margin-top: 1rem;">
            <div class="panel-title">Baixar o aplicativo</div>
            <div class="panel-subtitle">
                Use o arquivo abaixo para instalar a versão mais recente do app.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not files:
        st.info("Nenhuma build publicada ainda na pasta releases.")
        return

    for file_path in files:
        file_bytes = file_path.read_bytes()
        file_label = get_release_label(file_path)
        file_size = format_file_size(file_path.stat().st_size)
        st.download_button(
            label=f"{file_label} • {file_size}",
            data=file_bytes,
            file_name=file_path.name,
            mime="application/octet-stream",
            use_container_width=True,
            key=f"download_{file_path.name}",
        )

    st.caption(
        "Android costuma instalar normalmente com o APK de release. "
        "Para distribuição mais profissional, o ideal é assinar a release com seu próprio keystore."
    )


def render_public_home(public_dataframe: pd.DataFrame, auth_config: AuthConfig) -> None:
    _, top_action = st.columns([6, 1.7])

    with top_action:
        with st.popover("Área do funcionário", use_container_width=True):
            st.markdown(
                """
                <div class="login-card">
                    <div class="login-title">Área de edição</div>
                    <div class="login-subtitle">
                        Entre para cadastrar ou ajustar o cardápio.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not auth_config.is_configured:
                st.error("Login administrativo não configurado.")
                st.info(
                    "Configure usuários e senhas nos Secrets do Streamlit Cloud "
                    "ou no arquivo .streamlit/secrets.toml local."
                )
            else:
                with st.form("login_form", clear_on_submit=False):
                    username = st.text_input("Usuário")
                    password = st.text_input("Senha", type="password")
                    submitted = st.form_submit_button(
                        "Entrar para editar",
                        type="primary",
                        use_container_width=True,
                    )

                if submitted:
                    account = authenticate(username, password, auth_config)
                    if account is not None:
                        st.session_state["authenticated"] = True
                        st.session_state["auth_username"] = account.username
                        st.session_state["auth_role"] = account.role
                        st.rerun()
                    else:
                        st.error("Usuário ou senha inválidos.")

    _, center_col, _ = st.columns([1.15, 4.5, 1.15])

    with center_col:
        st.markdown(
            f"""
            <div class="public-shell">
                <div class="public-kicker">Cardápio da semana</div>
                <h1 class="public-title">{APP_NAME}</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_app_preview(
            public_dataframe,
            selectbox_key="public_preview_day",
            selectbox_label="Escolha o dia",
            show_panel=False,
        )

        render_downloads_section()


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
    if is_admin():
        col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1.15])
    else:
        col1, col2 = st.columns([1.45, 1])

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

    if is_admin():
        with col3:
            csv_data = normalize_dataframe(dataframe).to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Baixar CSV",
                data=csv_data,
                file_name="cardapio.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col4:
            if st.button("Preparar próxima semana", use_container_width=True):
                set_draft_dataframe(build_next_week_dataframe(dataframe))
                st.success(
                    "Nova semana criada com segunda a sexta e campos de comida em branco."
                )
                st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Painel do Cardápio",
        page_icon="🥗",
        layout="wide",
    )
    inject_css()
    public_dataframe = get_public_menu_dataframe()
    render_login_gate(public_dataframe)

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

    if is_admin():
        tab_quick, tab_table, tab_preview, tab_csv, tab_users, tab_templates = st.tabs(
            [
                "Edição rápida",
                "Tabela completa",
                "Prévia do app",
                "CSV",
                "Usuários",
                "Modelos e campos",
            ]
        )

        with tab_quick:
            render_quick_edit(get_draft_dataframe(), config.sheet_id)

        with tab_table:
            render_complete_editor(get_draft_dataframe())

        with tab_preview:
            render_app_preview(get_draft_dataframe())

        with tab_csv:
            render_csv_preview(get_draft_dataframe())

        with tab_users:
            render_user_management(config.sheet_id)

        with tab_templates:
            render_template_management(config.sheet_id)
    else:
        tab_quick, tab_preview = st.tabs(["Edição rápida", "Prévia do app"])

        with tab_quick:
            render_quick_edit(get_draft_dataframe(), config.sheet_id)

        with tab_preview:
            render_app_preview(get_draft_dataframe())


if __name__ == "__main__":
    main()
