import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from pathlib import Path
import io

# ---------- НАСТРОЙКА СТРАНИЦЫ ----------
st.set_page_config(
    page_title="Калькулятор уровня игроков",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Тёмная тема
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
PARAM_DESCRIPTIONS = {
    "Macro": "Видение карты, стратегическое мышление",
    "Comms": "Коммуникация, работа в команде",
    "1v1": "Навыки индивидуальной игры",
    "Mentality": "Психологическая устойчивость, стрессоустойчивость",
    "Reliability": "Надёжность, стабильность игры",
    "Comp exp": "Опыт выступлений на соревнованиях"
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
    next_tier = None
    next_threshold = 10.0
    sorted_tiers = sorted(tier_thresholds.items(), key=lambda x: x[1], reverse=True)
    for tier_name, threshold in sorted_tiers:
        if not np.isnan(avg_weighted) and avg_weighted >= threshold:
            tier = tier_name
            # находим следующий уровень (выше текущего)
            for t, th in sorted_tiers:
                if th > avg_weighted:
                    next_tier = t
                    next_threshold = th
                    break
            break
    # если игрок уже в Тир 1, следующего нет
    if tier == "Тир 1":
        next_tier = None
        next_threshold = None

    return {
        "param_avgs": param_avgs,
        "avg_unweighted": avg_unweighted,
        "avg_weighted": avg_weighted,
        "tier": tier,
        "next_tier": next_tier,
        "next_threshold": next_threshold
    }

# ---------- ФУНКЦИЯ ДЛЯ ПРОГРЕСС-БАРА ----------
def progress_to_next(result):
    if result["next_tier"] is not None and result["next_threshold"] is not None:
        current = result["avg_weighted"]
        nxt = result["next_threshold"]
        progress = min((current / nxt), 1.0)
        return progress, f"До {result['next_tier']} осталось {nxt - current:.1f} баллов"
    else:
        return 1.0, "Максимальный уровень!"

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
    st.dataframe(df, width='stretch')

    # Прогресс-бары для каждого игрока
    st.subheader("📊 Прогресс до следующего уровня")
    for player in players:
        result = calculate_player(player)
        progress, label = progress_to_next(result)
        st.progress(progress, text=f"{player['name']}: {label}")

    # Кнопки управления
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        confirm_delete_all = st.checkbox("Подтвердить удаление всех")
        if st.button("🗑️ Удалить всех игроков") and confirm_delete_all:
            players.clear()
            data["players"] = players
            save_data(data)
            st.rerun()
        elif st.button("🗑️ Удалить всех игроков") and not confirm_delete_all:
            st.warning("Поставьте галочку подтверждения")
    with col2:
        csv = df.drop(columns=["ID"]).to_csv(index=False, sep=';', decimal=',')
        st.download_button("📥 Скачать CSV", data=csv, file_name="players_ratings.csv", mime="text/csv")
        # Экспорт Excel
        try:
            import openpyxl
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.drop(columns=["ID"]).to_excel(writer, index=False, sheet_name='Players')
            excel_data = output.getvalue()
            st.download_button("📥 Скачать Excel", data=excel_data, file_name="players_ratings.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except ImportError:
            st.caption("Для Excel установите openpyxl: pip install openpyxl")
    with col4:
        # Сравнение игроков с мультивыбором
        if len(players) > 1:
            player_names = [p["name"] for p in players]
            selected_for_compare = st.multiselect("Выберите игроков для сравнения", player_names, default=player_names[:2] if len(player_names)>=2 else player_names)
            if selected_for_compare and len(selected_for_compare) > 1:
                fig_data = []
                for player in players:
                    if player["name"] in selected_for_compare:
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
                st.plotly_chart(fig, use_container_width=True)  # у plotly пока оставляем

    # Удаление конкретного игрока
    st.subheader("🗑️ Удалить игрока")
    player_names = [p["name"] for p in players]
    selected_to_delete = st.selectbox("Выберите игрока для удаления", player_names, key="delete_select")
    confirm_delete_one = st.checkbox("Подтвердить удаление", key="confirm_one")
    if st.button("Удалить выбранного игрока") and confirm_delete_one:
        for i, p in enumerate(players):
            if p["name"] == selected_to_delete:
                del players[i]
                break
        data["players"] = players
        save_data(data)
        st.success(f"Игрок {selected_to_delete} удалён!")
        st.rerun()
    elif st.button("Удалить выбранного игрока") and not confirm_delete_one:
        st.warning("Поставьте галочку подтверждения")

    # Гистограмма распределения уровней
    st.subheader("📊 Распределение по уровням")
    tiers = [calculate_player(p)["tier"] for p in players]
    tier_counts = pd.Series(tiers).value_counts().reset_index()
    tier_counts.columns = ["Тир", "Количество"]
    st.bar_chart(tier_counts.set_index("Тир"))

else:
    st.info("Пока нет добавленных игроков. Добавьте первого!")

# ---------- ФОРМА ДОБАВЛЕНИЯ / РЕДАКТИРОВАНИЯ ----------
st.subheader("➕ Добавить / Редактировать игрока")
st.caption("💡 Используйте таблицу для ввода оценок (каждая строка – оценщик, каждый столбец – параметр)")

edit_idx = st.session_state.get("edit_idx", None)
if edit_idx is not None and 0 <= edit_idx < len(players):
    player_edit = players[edit_idx]
    name_edit = player_edit["name"]
    ratings_edit = player_edit["ratings"]
    st.info(f"✏️ Редактируем игрока: {name_edit}")
else:
    name_edit = ""
    ratings_edit = {param: [10.0]*num_raters for param in weights.keys()}

# Создаём DataFrame для data_editor
params = list(weights.keys())
index_labels = [f"Оценщик {i+1}" for i in range(num_raters)]
default_df = pd.DataFrame(
    {param: ratings_edit.get(param, [10.0]*num_raters) for param in params},
    index=index_labels
)

with st.form(key="add_player_form"):
    name = st.text_input("Имя игрока", value=name_edit)
    # data_editor для оценок
    edited_df = st.data_editor(
        default_df,
        width='stretch',
        num_rows="fixed",
        key="ratings_editor"
    )

    col1, col2 = st.columns(2)
    with col1:
        submit = st.form_submit_button("✅ Добавить / Обновить")
    with col2:
        if edit_idx is not None:
            cancel_edit = st.form_submit_button("❌ Отменить редактирование")
        else:
            # Кнопка сброса формы – просто перезагружаем
            reset = st.form_submit_button("🔄 Сбросить форму")

    if submit and name.strip():
        # Преобразуем edited_df в словарь ratings
        ratings = {param: edited_df[param].tolist() for param in params}
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

    if 'reset' in locals() and reset:
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
    # Покажем описания параметров
    st.markdown("**Описание параметров:**")
    for param, desc in PARAM_DESCRIPTIONS.items():
        st.caption(f"**{param}** – {desc}")

# ---------- СБРОС НАСТРОЕК ----------
if st.sidebar.button("🔄 Сбросить веса и пороги по умолчанию"):
    data["weights"] = DEFAULT_PARAMS
    data["tiers"] = {"Тир 1": 9.0, "Тир 2": 8.0, "Тир 3": 7.0, "Тир 4": 6.0}
    save_data(data)
    st.rerun()