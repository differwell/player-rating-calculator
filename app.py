import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from pathlib import Path

# ---------- НАСТРОЙКА СТРАНИЦЫ ----------
st.set_page_config(
    page_title="Калькулятор уровня игроков",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Принудительная тёмная тема (через CSS)
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🏆 Калькулятор уровня игроков")
st.markdown("Оценка по 6 критериям с весами")

# ---------- НАСТРОЙКИ ПО УМОЛЧАНИЮ ----------
DEFAULT_PARAMS = {
    "Macro": 0.30,
    "Comms": 0.20,
    "1v1": 0.20,
    "Mentality": 0.10,
    "Reliability": 0.10,
    "Comp exp": 0.10
}
NUM_RATERS = 5
DATA_FILE = Path("data.json")

# ---------- ФУНКЦИИ РАБОТЫ С JSON ----------
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            st.warning("Файл данных повреждён или пуст. Будет создан новый.")
            default_data = {
                "players": [],
                "weights": DEFAULT_PARAMS,
                "tiers": {"Тир 1": 9.0, "Тир 2": 8.0, "Тир 3": 7.0, "Тир 4": 6.0}
            }
            save_data(default_data)
            return default_data
    else:
        default_data = {
            "players": [],
            "weights": DEFAULT_PARAMS,
            "tiers": {"Тир 1": 9.0, "Тир 2": 8.0, "Тир 3": 7.0, "Тир 4": 6.0}
        }
        save_data(default_data)
        return default_data

# ---------- ЗАГРУЗКА ДАННЫХ ----------
data = load_data()
players = data.get("players", [])
weights = data.get("weights", DEFAULT_PARAMS)
tier_thresholds = data.get("tiers", {"Тир 1": 9.0, "Тир 2": 8.0, "Тир 3": 7.0, "Тир 4": 6.0})

# ---------- БОКОВАЯ ПАНЕЛЬ ----------
st.sidebar.header("⚙️ Настройки")
num_raters = st.sidebar.number_input("Количество оценщиков", min_value=1, max_value=10, value=NUM_RATERS, step=1)

st.sidebar.subheader("Веса параметров")
new_weights = {}
for param, default_w in DEFAULT_PARAMS.items():
    w = st.sidebar.slider(f"{param} (%)", 0, 100, int(weights.get(param, default_w)*100), step=5)
    new_weights[param] = w / 100.0

if new_weights != weights:
    weights = new_weights
    data["weights"] = weights
    save_data(data)

st.sidebar.subheader("Пороги уровней (Тир)")
new_tiers = {}
for tier_name, default_threshold in tier_thresholds.items():
    new_tiers[tier_name] = st.sidebar.slider(f"{tier_name} (мин. балл)", 5.0, 10.0, default_threshold, step=0.1)

if new_tiers != tier_thresholds:
    tier_thresholds = new_tiers
    data["tiers"] = tier_thresholds
    save_data(data)

# ---------- ФУНКЦИЯ РАСЧЁТА ----------
def calculate_player(player_data):
    ratings = player_data["ratings"]
    param_avgs = {}
    for param in weights.keys():
        scores = ratings.get(param, [np.nan]*num_raters)
        valid = [s for s in scores if not np.isnan(s)]
        avg = np.mean(valid) if valid else np.nan
        param_avgs[param] = avg

    avg_unweighted = np.nanmean(list(param_avgs.values()))
    weighted_sum = 0.0
    total_weight = 0.0
    for param, avg_val in param_avgs.items():
        w = weights.get(param, 0)
        if not np.isnan(avg_val):
            weighted_sum += avg_val * w
            total_weight += w
    avg_weighted = weighted_sum / total_weight if total_weight > 0 else np.nan

    tier = "Тир 5 (базовый)"
    for tier_name, threshold in sorted(tier_thresholds.items(), key=lambda x: x[1], reverse=True):
        if not np.isnan(avg_weighted) and avg_weighted >= threshold:
            tier = tier_name
            break

    return {
        "param_avgs": param_avgs,
        "avg_unweighted": avg_unweighted,
        "avg_weighted": avg_weighted,
        "tier": tier
    }

# ---------- ОТОБРАЖЕНИЕ СПИСКА ----------
st.subheader("📋 Список игроков")

if players:
    rows = []
    for idx, player in enumerate(players):
        result = calculate_player(player)
        row = {
            "ID": idx,
            "Игрок": player["name"],
            "Средний (без веса)": f"{result['avg_unweighted']:.2f}" if not np.isnan(result['avg_unweighted']) else "-",
            "Итоговый (с весом)": f"{result['avg_weighted']:.2f}" if not np.isnan(result['avg_weighted']) else "-",
            "Тир": result["tier"]
        }
        for param in weights.keys():
            val = result["param_avgs"].get(param, np.nan)
            row[param] = f"{val:.2f}" if not np.isnan(val) else "-"
        rows.append(row)

    df = pd.DataFrame(rows)
    cols = ["ID", "Игрок"] + list(weights.keys()) + ["Средний (без веса)", "Итоговый (с весом)", "Тир"]
    df = df[cols]
    st.dataframe(df, use_container_width=True)

    # Кнопки управления
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        if st.button("🗑️ Удалить всех игроков"):
            players.clear()
            data["players"] = players
            save_data(data)
            st.rerun()
    with col2:
        csv = df.drop(columns=["ID"]).to_csv(index=False, sep=';', decimal=',')
        st.download_button("📥 Скачать CSV", data=csv, file_name="players_ratings.csv", mime="text/csv")
    with col4:
        if len(players) > 1:
            if st.button("📊 Сравнить игроков"):
                fig_data = []
                for player in players:
                    result = calculate_player(player)
                    fig_data.append({"Игрок": player["name"], **result["param_avgs"]})
                fig_df = pd.DataFrame(fig_data)
                fig = px.line_polar(
                    fig_df.melt(id_vars=["Игрок"], value_vars=list(weights.keys()), var_name="Параметр", value_name="Оценка"),
                    r="Оценка",
                    theta="Параметр",
                    color="Игрок",
                    line_close=True,
                    title="Радарная диаграмма игроков"
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Добавьте больше игроков для сравнения.")

    # ---------- УДАЛЕНИЕ КОНКРЕТНОГО ИГРОКА ----------
    st.subheader("🗑️ Удалить игрока")
    player_names = [p["name"] for p in players]
    selected_to_delete = st.selectbox("Выберите игрока для удаления", player_names, key="delete_select")
    if st.button("Удалить выбранного игрока"):
        for i, p in enumerate(players):
            if p["name"] == selected_to_delete:
                del players[i]
                break
        data["players"] = players
        save_data(data)
        st.success(f"Игрок {selected_to_delete} удалён!")
        st.rerun()

else:
    st.info("Пока нет добавленных игроков. Добавьте первого!")

# ---------- ФОРМА ДОБАВЛЕНИЯ / РЕДАКТИРОВАНИЯ ----------
st.subheader("➕ Добавить нового игрока")
st.caption("💡 По умолчанию оценки выставлены на 10 – вы можете их изменить.")

edit_idx = st.session_state.get("edit_idx", None)
if edit_idx is not None and 0 <= edit_idx < len(players):
    player_edit = players[edit_idx]
    name_edit = player_edit["name"]
    ratings_edit = player_edit["ratings"]
    st.info(f"✏️ Редактируем игрока: {name_edit}")
else:
    name_edit = ""
    ratings_edit = {param: [10.0]*num_raters for param in weights.keys()}

with st.form(key="add_player_form"):
    name = st.text_input("Имя игрока", value=name_edit)
    ratings = {}
    for i, (param, w) in enumerate(weights.items()):
        st.write(f"**{param}** (вес {w*100:.0f}%)")
        scores = []
        default_scores = ratings_edit.get(param, [10.0]*num_raters)
        for r in range(num_raters):
            val = st.number_input(
                f"Оценщик {r+1}",
                min_value=0.0,
                max_value=10.0,
                value=float(default_scores[r]) if r < len(default_scores) else 10.0,
                step=0.5,
                key=f"{param}_{r}_{edit_idx or 0}_{i}"
            )
            scores.append(val)
        ratings[param] = scores

    col1, col2 = st.columns(2)
    with col1:
        submit = st.form_submit_button("✅ Добавить / Обновить")
    with col2:
        if edit_idx is not None:
            cancel_edit = st.form_submit_button("❌ Отменить редактирование")

    if submit and name.strip():
        player_data = {"name": name.strip(), "ratings": ratings}
        if edit_idx is not None and 0 <= edit_idx < len(players):
            players[edit_idx] = player_data
            st.session_state["edit_idx"] = None
        else:
            players.append(player_data)
        data["players"] = players
        save_data(data)
        st.success(f"Игрок {name} сохранён!")
        st.rerun()
    elif submit:
        st.error("Введите имя игрока")

    if 'cancel_edit' in locals() and cancel_edit and edit_idx is not None:
        st.session_state["edit_idx"] = None
        st.rerun()

# ---------- РЕДАКТИРОВАНИЕ (выбор из списка) ----------
if players:
    st.subheader("✏️ Редактировать игрока")
    player_names = [p["name"] for p in players]
    selected = st.selectbox("Выберите игрока для редактирования", player_names)
    if st.button("📝 Редактировать"):
        idx = player_names.index(selected)
        st.session_state["edit_idx"] = idx
        st.rerun()

# ---------- ИНФОРМАЦИЯ О ФОРМУЛЕ ----------
with st.expander("📐 Как рассчитывается итоговый балл?"):
    st.markdown("""
    **1. Средняя оценка по параметру** – среднее арифметическое оценок всех оценщиков.  
    **2. Средний балл (без веса)** – среднее арифметическое средних оценок по всем параметрам.  
    **3. Итоговый балл (с весом)** – сумма (средняя_по_параметру × вес_параметра) / сумма_весов.  
    **4. Уровень (Тир)** – определяется по шкале, заданной в настройках.
    """)

# ---------- СБРОС НАСТРОЕК ----------
if st.sidebar.button("🔄 Сбросить веса и пороги по умолчанию"):
    data["weights"] = DEFAULT_PARAMS
    data["tiers"] = {"Тир 1": 9.0, "Тир 2": 8.0, "Тир 3": 7.0, "Тир 4": 6.0}
    save_data(data)
    st.rerun()