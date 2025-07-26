import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px

# --- KONFIGURASI DASAR ---
st.set_page_config(layout="wide", page_title="Habit Tracker Ibadah")

# Nama file database Excel
DB_FILE = "habit_tracker_database.xlsx"

# DAFTAR PESERTA YANG SUDAH DITENTUKAN
PARTICIPANTS = [
    "Sahrul", "Umam", "Fatih", "Fahmi", "El", "Taqi",
    "Bang Abror", "Bang Habib", "Bang Yafie", "Bang Yudo"
]

# Daftar Ibadah dan Targetnya
HABITS = {
    "Juz 30 (Hafalan/Murajaah)": "daily",
    "Hadis Arbain 1-25": "daily",
    "Tilawah 1/2 Juz": "daily",
    "Al-Matsurat (Pagi/Sore)": "daily",
    "Qiyamulail": "weekly",
    "Olahraga": "weekly",
    "Shaum Sunnah": "monthly"
}

TARGETS = {
    "Qiyamulail": 2, # per pekan
    "Olahraga": 3, # per pekan
    "Shaum Sunnah": 3 # per bulan
}

# --- FUNGSI UNTUK MEMBACA DAN MENULIS DATA ---

@st.cache_data(ttl=60)
def load_data_from_excel(username):
    """Memuat data dari sheet spesifik user di file Excel."""
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=["Tanggal"] + list(HABITS.keys()))
    try:
        df = pd.read_excel(DB_FILE, sheet_name=username)
    except ValueError:
        return pd.DataFrame(columns=["Tanggal"] + list(HABITS.keys()))
    if not df.empty:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'])
    return df

@st.cache_data(ttl=60)
def load_all_user_data(db_file):
    """Memuat data dari SEMUA sheet di file Excel untuk leaderboard."""
    if not os.path.exists(db_file):
        return pd.DataFrame()
    
    xls = pd.ExcelFile(db_file)
    all_data = []
    # Hanya baca sheet yang namanya ada di daftar peserta
    for sheet_name in xls.sheet_names:
        if sheet_name in PARTICIPANTS:
            try:
                df_user = pd.read_excel(xls, sheet_name=sheet_name)
                df_user['User'] = sheet_name
                all_data.append(df_user)
            except Exception as e:
                st.warning(f"Gagal membaca sheet '{sheet_name}': {e}")
    
    if not all_data:
        return pd.DataFrame()
        
    master_df = pd.concat(all_data, ignore_index=True)
    master_df['Tanggal'] = pd.to_datetime(master_df['Tanggal'])
    return master_df

def save_data_to_excel(df, username):
    """Menyimpan DataFrame ke sheet spesifik user."""
    df_to_save = df.copy()
    df_to_save['Tanggal'] = df_to_save['Tanggal'].dt.strftime('%Y-%m-%d')
    mode = 'a' if os.path.exists(DB_FILE) else 'w'
    with pd.ExcelWriter(DB_FILE, mode=mode, engine='openpyxl', if_sheet_exists='replace' if mode=='a' else None) as writer:
        df_to_save.to_excel(writer, sheet_name=username, index=False)

# --- UI UTAMA ---
st.title("🕌 Habit Tracker Ibadah")
st.markdown("Catat dan pantau perkembangan ibadah harian, mingguan, dan bulanan Anda.")

# Sidebar
with st.sidebar:
    st.header("👤 Pengguna")
    # MENGGANTI TEXT INPUT MENJADI DROPDOWN/SELECTBOX
    username = st.selectbox(
        "Pilih Nama Peserta",
        options=PARTICIPANTS,
        index=0, # Nama pertama sebagai default
        key="username_select"
    )
    st.info("Pilih nama Anda untuk mengisi jurnal atau melihat progress.")
    
    today_date = datetime.now().date()
    start_of_week = today_date - timedelta(days=today_date.weekday()) 
    
    st.header("🗓️ Pilih Tanggal Input")
    selected_date = st.date_input(
        "Pilih tanggal untuk diisi", value=today_date,
        min_value=start_of_week, max_value=start_of_week + timedelta(days=6),
        help="Anda hanya bisa mengisi jurnal untuk pekan ini."
    )

# --- MEMUAT DATA PENGGUNA SAAT INI ---
df = load_data_from_excel(username)

# --- FORM INPUT JURNAL HARIAN ---
st.header(f"Jurnal untuk: {selected_date.strftime('%A, %d %B %Y')}")

date_str = selected_date.strftime('%Y-%m-%d')
if not df.empty and pd.to_datetime(date_str) in df['Tanggal'].values:
    daily_data = df[df['Tanggal'] == pd.to_datetime(date_str)].iloc[0].to_dict()
else:
    daily_data = {habit: False for habit in HABITS}

with st.form(key="daily_journal_form"):
    st.subheader("Ibadah Harian")
    cols_daily = st.columns(2)
    daily_habits = {k: v for k, v in HABITS.items() if v == 'daily'}
    for i, (habit, _) in enumerate(daily_habits.items()):
        daily_data[habit] = cols_daily[i % 2].checkbox(habit, value=bool(daily_data.get(habit, 0)))
    
    st.subheader("Ibadah Non-Harian (Jika dilakukan hari ini)")
    cols_non_daily = st.columns(3)
    non_daily_habits = {k: v for k, v in HABITS.items() if v != 'daily'}
    for i, (habit, _) in enumerate(non_daily_habits.items()):
        daily_data[habit] = cols_non_daily[i].checkbox(habit, value=bool(daily_data.get(habit, 0)))

    submitted = st.form_submit_button("✅ Simpan Jurnal")

# --- LOGIKA PENYIMPANAN DATA ---
if submitted:
    new_row_data = {"Tanggal": pd.to_datetime(date_str)}
    for habit in HABITS:
        new_row_data[habit] = 1 if daily_data.get(habit, False) else 0

    if not df.empty and pd.to_datetime(date_str) in df['Tanggal'].values:
        df.loc[df['Tanggal'] == pd.to_datetime(date_str)] = pd.Series(new_row_data).values
    else:
        new_row = pd.DataFrame([new_row_data])
        df = pd.concat([df, new_row], ignore_index=True)

    df = df.sort_values(by="Tanggal").reset_index(drop=True)
    save_data_to_excel(df, username)
    st.success("✨ Jurnal berhasil disimpan ke file Excel!")
    st.cache_data.clear()
    st.rerun()

# --- VISUALISASI DAN LEADERBOARD ---
st.markdown("---")

tab1, tab2, tab3 = st.tabs([f"📊 Progress Pekanan ({username})", f"🗓️ Progress Bulanan ({username})", "🏆 Leaderboard"])

with tab1:
    if df.empty:
        st.info("Belum ada data untuk pekan ini.")
    else:
        today_date = datetime.now().date()
        start_of_week = today_date - timedelta(days=today_date.weekday())
        weekly_df = df[df['Tanggal'].dt.date >= start_of_week]
        
        if weekly_df.empty:
            st.info("Belum ada data untuk pekan ini.")
        else:
            progress_data = []
            total_target_weekly = 0
            total_actual_weekly = weekly_df[list(HABITS.keys())].sum().sum()
            for habit, type in HABITS.items():
                if type == 'monthly': continue
                actual = weekly_df[habit].sum()
                target = TARGETS[habit] if type == 'weekly' else 7
                total_target_weekly += target
                percentage = (actual / target * 100) if target > 0 else 0
                progress_data.append({"Ibadah": habit, "Capaian (%)": percentage})
            
            progress_df_weekly = pd.DataFrame(progress_data)
            
            col1, col2 = st.columns([3, 2])
            with col1:
                st.subheader("Perbandingan Capaian Ibadah")
                fig_bar = px.bar(progress_df_weekly, x="Capaian (%)", y="Ibadah", orientation='h', text="Capaian (%)", color="Capaian (%)", color_continuous_scale=px.colors.sequential.Greens)
                fig_bar.update_traces(texttemplate='%{x:.0f}%', textposition='inside')
                fig_bar.update_layout(uniformtext_minsize=8, xaxis_range=[0,100], yaxis={'categoryorder':'total ascending'}, coloraxis_showscale=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            with col2:
                st.subheader("Progress Keseluruhan")
                remaining_weekly = max(0, total_target_weekly - total_actual_weekly)
                pie_data = pd.DataFrame({"Status": ["Selesai", "Belum Selesai"], "Jumlah": [total_actual_weekly, remaining_weekly]})
                fig_pie = px.pie(pie_data, values="Jumlah", names="Status", hole=0.4, color_discrete_map={"Selesai": "green", "Belum Selesai": "lightgray"})
                st.plotly_chart(fig_pie, use_container_width=True)

with tab2:
    if df.empty:
        st.info("Belum ada data untuk bulan ini.")
    else:
        today_date = datetime.now().date()
        start_of_month = today_date.replace(day=1)
        monthly_df = df[df['Tanggal'].dt.date >= start_of_month]

        if monthly_df.empty:
            st.info("Belum ada data untuk bulan ini.")
        else:
            progress_data = []
            total_target_monthly = 0
            total_actual_monthly = monthly_df[list(HABITS.keys())].sum().sum()
            days_passed = today_date.day
            num_weeks_passed = days_passed / 7
            for habit, type in HABITS.items():
                actual = monthly_df[habit].sum()
                target = 0
                if type == "daily": target = days_passed
                elif type == "weekly": target = TARGETS[habit] * num_weeks_passed
                elif type == "monthly": target = TARGETS[habit]
                total_target_monthly += target
                percentage = (actual / target * 100) if target > 0 else 0
                progress_data.append({"Ibadah": habit, "Capaian (%)": percentage})
            
            progress_df_monthly = pd.DataFrame(progress_data)
            
            col1, col2 = st.columns([3, 2])
            with col1:
                st.subheader("Perbandingan Capaian Ibadah")
                fig_bar = px.bar(progress_df_monthly, x="Capaian (%)", y="Ibadah", orientation='h', text="Capaian (%)", color="Capaian (%)", color_continuous_scale=px.colors.sequential.Blues)
                fig_bar.update_traces(texttemplate='%{x:.0f}%', textposition='inside')
                fig_bar.update_layout(uniformtext_minsize=8, xaxis_range=[0,100], yaxis={'categoryorder':'total ascending'}, coloraxis_showscale=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            with col2:
                st.subheader("Progress Keseluruhan")
                remaining_monthly = max(0, total_target_monthly - total_actual_monthly)
                pie_data = pd.DataFrame({"Status": ["Selesai", "Belum Selesai"], "Jumlah": [total_actual_monthly, remaining_monthly]})
                fig_pie = px.pie(pie_data, values="Jumlah", names="Status", hole=0.4, color_discrete_map={"Selesai": "royalblue", "Belum Selesai": "lightgray"})
                st.plotly_chart(fig_pie, use_container_width=True)

with tab3:
    st.header("🏆 Papan Peringkat Peserta")
    all_users_df = load_all_user_data(DB_FILE)

    if all_users_df.empty:
        st.warning("Belum ada data dari peserta manapun untuk ditampilkan di leaderboard.")
    else:
        today_date = datetime.now().date()
        
        # --- Leaderboard Pekanan ---
        st.subheader("Peringkat Pekan Ini")
        start_of_week = today_date - timedelta(days=today_date.weekday())
        weekly_data_all = all_users_df[all_users_df['Tanggal'].dt.date >= start_of_week]
        
        leaderboard_weekly = []
        if not weekly_data_all.empty:
            for user, group in weekly_data_all.groupby('User'):
                total_actual = group[list(HABITS.keys())].sum().sum()
                total_target = 0
                for habit, type in HABITS.items():
                    if type == "daily": total_target += 7
                    elif type == "weekly": total_target += TARGETS[habit]
                
                percentage = (total_actual / total_target * 100) if total_target > 0 else 0
                leaderboard_weekly.append({"Peserta": user, "Progress (%)": round(percentage, 2)})

            lb_df_w = pd.DataFrame(leaderboard_weekly).sort_values("Progress (%)", ascending=False).reset_index(drop=True)
            lb_df_w.index += 1
            
            col1, col2 = st.columns(2)
            with col1: st.dataframe(lb_df_w, use_container_width=True)
            with col2:
                fig = px.bar(lb_df_w, x="Progress (%)", y="Peserta", orientation='h', title="Visualisasi Peringkat Pekanan", text='Progress (%)')
                fig.update_traces(texttemplate='%{text:.1f}%')
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_range=[0,100])
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data pekan ini untuk leaderboard.")

        st.markdown("---")

        # --- Leaderboard Bulanan ---
        st.subheader("Peringkat Bulan Ini")
        start_of_month = today_date.replace(day=1)
        monthly_data_all = all_users_df[all_users_df['Tanggal'].dt.date >= start_of_month]
        
        leaderboard_monthly = []
        if not monthly_data_all.empty:
            days_passed = today_date.day
            num_weeks_passed = days_passed / 7
            
            for user, group in monthly_data_all.groupby('User'):
                total_actual = group[list(HABITS.keys())].sum().sum()
                total_target = 0
                for habit, type in HABITS.items():
                    if type == "daily": total_target += days_passed
                    elif type == "weekly": total_target += TARGETS[habit] * num_weeks_passed
                    elif type == "monthly": total_target += TARGETS[habit]
                percentage = (total_actual / total_target * 100) if total_target > 0 else 0
                leaderboard_monthly.append({"Peserta": user, "Progress (%)": round(percentage, 2)})

            lb_df_m = pd.DataFrame(leaderboard_monthly).sort_values("Progress (%)", ascending=False).reset_index(drop=True)
            lb_df_m.index += 1
            
            col1, col2 = st.columns(2)
            with col1: st.dataframe(lb_df_m, use_container_width=True)
            with col2:
                fig = px.bar(lb_df_m, x="Progress (%)", y="Peserta", orientation='h', title="Visualisasi Peringkat Bulanan", text='Progress (%)', color="Progress (%)", color_continuous_scale=px.colors.sequential.Blues)
                fig.update_traces(texttemplate='%{text:.1f}%')
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_range=[0,100])
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data bulan ini untuk leaderboard.")