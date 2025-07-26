import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os # Digunakan untuk mengecek keberadaan file

# --- KONFIGURASI DASAR ---
st.set_page_config(layout="wide", page_title="Habit Tracker Ibadah")

# Nama file database Excel
DB_FILE = "habit_tracker_database.xlsx"

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

# --- FUNGSI UNTUK MEMBACA DAN MENULIS KE EXCEL ---

@st.cache_data(ttl=60) # Cache data selama 60 detik
def load_data_from_excel(username):
    """
    Memuat data dari sheet spesifik user di file Excel.
    Jika file atau sheet tidak ada, buat yang baru.
    """
    if not os.path.exists(DB_FILE):
        # Jika file tidak ada sama sekali, buat DataFrame kosong
        return pd.DataFrame(columns=["Tanggal"] + list(HABITS.keys()))

    try:
        # Baca sheet spesifik milik user
        df = pd.read_excel(DB_FILE, sheet_name=username)
    except ValueError:
        # Error ini terjadi jika sheet dengan nama 'username' tidak ada
        return pd.DataFrame(columns=["Tanggal"] + list(HABITS.keys()))

    if not df.empty:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'])
    return df

def save_data_to_excel(df, username):
    """
    Menyimpan DataFrame ke sheet spesifik user di file Excel.
    Sheet lain di dalam file yang sama tidak akan terpengaruh.
    """
    # Buat salinan untuk menghindari mengubah df di cache streamlit
    df_to_save = df.copy()
    # Format tanggal sebagai string agar kompatibel dengan Excel
    df_to_save['Tanggal'] = df_to_save['Tanggal'].dt.strftime('%Y-%m-%d')

    # Gunakan ExcelWriter untuk menyimpan ke sheet spesifik tanpa menimpa yang lain
    try:
        with pd.ExcelWriter(DB_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            df_to_save.to_excel(writer, sheet_name=username, index=False)
    except FileNotFoundError:
        # Jika file belum ada, gunakan mode 'w' (write) untuk membuatnya
         with pd.ExcelWriter(DB_FILE, mode='w', engine='openpyxl') as writer:
            df_to_save.to_excel(writer, sheet_name=username, index=False)


# --- TAMPILAN UTAMA (UI) ---
st.title("🕌 Habit Tracker Ibadah (Versi Excel)")
st.markdown("Catat dan pantau perkembangan ibadah harian, mingguan, dan bulanan Anda.")

# --- SIDEBAR UNTUK INPUT PENGGUNA ---
with st.sidebar:
    st.header("👤 Pengguna")
    username = st.text_input("Masukkan Nama Anda", key="username_input")
    st.info("Setiap nama akan dibuatkan sheet-nya sendiri di file Excel. Pastikan nama yang dimasukkan selalu sama.")
    
    # Menentukan rentang tanggal minggu ini
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    st.header("🗓️ Pilih Tanggal")
    selected_date = st.date_input(
        "Pilih tanggal untuk diisi",
        value=today,
        min_value=start_of_week,
        max_value=start_of_week + timedelta(days=6),
        help="Anda hanya bisa mengisi jurnal untuk pekan ini."
    )

if not username:
    st.info("👈 Silakan masukkan nama Anda di sidebar untuk memulai.")
    st.stop()

# --- MEMUAT DATA ---
df = load_data_from_excel(username)

# --- FORM INPUT JURNAL HARIAN ---
st.header(f"Jurnal untuk {selected_date.strftime('%A, %d %B %Y')}")

# Cek apakah data untuk tanggal terpilih sudah ada
date_str = selected_date.strftime('%Y-%m-%d')
if not df.empty and pd.to_datetime(date_str) in df['Tanggal'].values:
    daily_data = df[df['Tanggal'] == pd.to_datetime(date_str)].iloc[0].to_dict()
else:
    daily_data = {habit: False for habit in HABITS} # Default value

with st.form(key="daily_journal_form"):
    st.subheader("Ibadah Harian")
    cols = st.columns(2)
    daily_habits = {k: v for k, v in HABITS.items() if v == 'daily'}
    for i, (habit, _) in enumerate(daily_habits.items()):
        daily_data[habit] = cols[i % 2].checkbox(habit, value=bool(daily_data.get(habit, 0))) # Ubah 0/1 ke bool
    
    st.subheader("Ibadah Non-Harian (Jika dilakukan hari ini)")
    cols = st.columns(3)
    non_daily_habits = {k: v for k, v in HABITS.items() if v != 'daily'}
    for i, (habit, _) in enumerate(non_daily_habits.items()):
        daily_data[habit] = cols[i].checkbox(habit, value=bool(daily_data.get(habit, 0))) # Ubah 0/1 ke bool

    submitted = st.form_submit_button("✅ Simpan Jurnal")

# --- LOGIKA PENYIMPANAN DATA ---
if submitted:
    new_row_data = {"Tanggal": pd.to_datetime(date_str)}
    for habit in HABITS:
        # Konversi boolean Python ke 1 (True) atau 0 (False) untuk kemudahan agregasi
        new_row_data[habit] = 1 if daily_data.get(habit, False) else 0

    new_row = pd.DataFrame([new_row_data])

    if not df.empty and pd.to_datetime(date_str) in df['Tanggal'].values:
        # Update baris yang sudah ada
        df.loc[df['Tanggal'] == pd.to_datetime(date_str), list(new_row_data.keys())] = list(new_row_data.values())
    else:
        # Tambah baris baru
        df = pd.concat([df, new_row], ignore_index=True)

    df = df.sort_values(by="Tanggal").reset_index(drop=True)
    save_data_to_excel(df, username)
    st.success("✨ Jurnal berhasil disimpan ke file Excel!")
    # Clear cache agar data yang ditampilkan selalu fresh setelah disimpan
    st.cache_data.clear()
    st.rerun()


# --- VISUALISASI PROGRESS ---
# Tambahkan ini di bagian atas file Anda
import plotly.express as px


# --- VISUALISASI PROGRESS ---
st.markdown("---")
st.header("📊 Visualisasi Progress")

if df.empty:
    st.warning("Belum ada data untuk ditampilkan. Silakan isi jurnal harian Anda terlebih dahulu.")
else:
    # --- Filter data untuk pekan dan bulan ini ---
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week_dt = pd.to_datetime(start_of_week)
    end_of_week_dt = start_of_week_dt + timedelta(days=6)
    
    start_of_month = today.replace(day=1)
    start_of_month_dt = pd.to_datetime(start_of_month)
    
    weekly_df = df[(df['Tanggal'] >= start_of_week_dt) & (df['Tanggal'] <= end_of_week_dt)]
    monthly_df = df[df['Tanggal'] >= start_of_month_dt]

    # --- TABS UNTUK VISUALISASI PEKANAN DAN BULANAN ---
    tab1, tab2 = st.tabs(["📊 Progress Pekan Ini", "🗓️ Progress Bulan Ini"])

    with tab1:
        if weekly_df.empty:
            st.info("Belum ada data untuk pekan ini.")
        else:
            progress_data = []
            total_target_weekly = 0
            total_actual_weekly = weekly_df[list(HABITS.keys())].sum().sum()

            for habit, type in HABITS.items():
                actual = weekly_df[habit].sum()
                target = 0
                if type == "daily":
                    target = 7
                elif type == "weekly":
                    target = TARGETS[habit]
                # Target bulanan tidak dihitung dalam progress pekanan
                else:
                    continue

                total_target_weekly += target
                percentage = (actual / target * 100) if target > 0 else 0
                progress_data.append({"Ibadah": habit, "Capaian (%)": percentage, "Detail": f"{int(actual)} dari {int(target)}"})
            
            progress_df_weekly = pd.DataFrame(progress_data)

            # --- Visualisasi Pekanan ---
            col1, col2 = st.columns([3, 2]) # Beri lebih banyak ruang untuk bar chart

            with col1:
                st.subheader("Perbandingan Capaian Ibadah")
                fig_bar_weekly = px.bar(
                    progress_df_weekly,
                    x="Capaian (%)",
                    y="Ibadah",
                    orientation='h',
                    text="Capaian (%)",
                    color="Capaian (%)",
                    color_continuous_scale=px.colors.sequential.Greens
                )
                fig_bar_weekly.update_traces(texttemplate='%{x:.0f}%', textposition='inside')
                fig_bar_weekly.update_layout(
                    uniformtext_minsize=8, uniformtext_mode='hide',
                    xaxis_range=[0,100],
                    yaxis={'categoryorder':'total ascending'},
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_bar_weekly, use_container_width=True)

            with col2:
                st.subheader("Progress Keseluruhan")
                remaining_weekly = max(0, total_target_weekly - total_actual_weekly)
                pie_data_weekly = pd.DataFrame({
                    "Status": ["Selesai", "Belum Selesai"],
                    "Jumlah": [total_actual_weekly, remaining_weekly]
                })
                fig_pie_weekly = px.pie(
                    pie_data_weekly,
                    values="Jumlah",
                    names="Status",
                    hole=0.4, # Membuatnya seperti donut chart
                    color_discrete_map={"Selesai": "green", "Belum Selesai": "lightgray"}
                )
                st.plotly_chart(fig_pie_weekly, use_container_width=True)

    with tab2:
        if monthly_df.empty:
            st.info("Belum ada data untuk bulan ini.")
        else:
            progress_data = []
            total_target_monthly = 0
            total_actual_monthly = monthly_df[list(HABITS.keys())].sum().sum()
            days_passed = today.day
            num_weeks_passed = (days_passed / 7)

            for habit, type in HABITS.items():
                actual = monthly_df[habit].sum()
                target = 0
                if type == "daily":
                    target = days_passed
                elif type == "weekly":
                    target = TARGETS[habit] * num_weeks_passed
                elif type == "monthly":
                    target = TARGETS[habit]

                total_target_monthly += target
                percentage = (actual / target * 100) if target > 0 else 0
                progress_data.append({"Ibadah": habit, "Capaian (%)": percentage, "Detail": f"{int(actual)} dari {int(target)}"})

            progress_df_monthly = pd.DataFrame(progress_data)

            # --- Visualisasi Bulanan ---
            col1, col2 = st.columns([3, 2])

            with col1:
                st.subheader("Perbandingan Capaian Ibadah")
                fig_bar_monthly = px.bar(
                    progress_df_monthly,
                    x="Capaian (%)",
                    y="Ibadah",
                    orientation='h',
                    text="Capaian (%)",
                    color="Capaian (%)",
                    color_continuous_scale=px.colors.sequential.Blues
                )
                fig_bar_monthly.update_traces(texttemplate='%{x:.0f}%', textposition='inside')
                fig_bar_monthly.update_layout(
                    uniformtext_minsize=8, uniformtext_mode='hide',
                    xaxis_range=[0,100],
                    yaxis={'categoryorder':'total ascending'},
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_bar_monthly, use_container_width=True)

            with col2:
                st.subheader("Progress Keseluruhan")
                remaining_monthly = max(0, total_target_monthly - total_actual_monthly)
                pie_data_monthly = pd.DataFrame({
                    "Status": ["Selesai", "Belum Selesai"],
                    "Jumlah": [total_actual_monthly, remaining_monthly]
                })
                fig_pie_monthly = px.pie(
                    pie_data_monthly,
                    values="Jumlah",
                    names="Status",
                    hole=0.4,
                    color_discrete_map={"Selesai": "royalblue", "Belum Selesai": "lightgray"}
                )
                st.plotly_chart(fig_pie_monthly, use_container_width=True)