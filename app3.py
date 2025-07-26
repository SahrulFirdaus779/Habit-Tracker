import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import io
from fpdf import FPDF
import plotly.express as px

# --- KONFIGURASI DASAR ---
st.set_page_config(layout="wide", page_title="LetsTracker")

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
EXTRA_COLS = ["Catatan"]

TARGETS = {
    "Qiyamulail": 2,
    "Olahraga": 3,
    "Shaum Sunnah": 3
}

# --- FUNGSI BANTUAN ---

def calculate_streaks(df):
    """Menghitung streak untuk setiap ibadah harian."""
    streaks = {}
    daily_habits = {k for k, v in HABITS.items() if v == 'daily'}
    if df.empty or not daily_habits:
        for habit in daily_habits: streaks[habit] = 0
        return streaks

    df_sorted = df.sort_values(by="Tanggal", ascending=False).reset_index(drop=True)
    today = datetime.now().date()
    
    last_entry_date = df_sorted.loc[0, 'Tanggal'].date()
    if last_entry_date < today - timedelta(days=1):
        for habit in daily_habits: streaks[habit] = 0
        return streaks

    for habit in daily_habits:
        streak_count = 0
        expected_date = last_entry_date
        if df_sorted.loc[0, habit] == 1:
            for _, row in df_sorted.iterrows():
                if row.get(habit, 0) == 1 and row['Tanggal'].date() == expected_date:
                    streak_count += 1
                    expected_date -= timedelta(days=1)
                else:
                    break
        streaks[habit] = streak_count
    return streaks

def df_to_pdf(df, title="Laporan Progress"):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, 0, 1, "C")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 7)
    headers = df.columns.tolist()
    col_widths = {'Tanggal': 25, 'Catatan': 50}
    num_habit_cols = len(headers) - len(col_widths)
    default_width = (297 - 20 - sum(col_widths.values())) / num_habit_cols if num_habit_cols > 0 else 20
    for header in headers:
        width = col_widths.get(header, default_width)
        pdf.cell(width, 10, header, 1, 0, "C")
    pdf.ln()
    pdf.set_font("Arial", "", 7)
    for _, row in df.iterrows():
        for header in headers:
            width = col_widths.get(header, default_width)
            cell_text = row[header].strftime('%Y-%m-%d') if isinstance(row[header], (pd.Timestamp, datetime)) else str(row[header])
            pdf.cell(width, 10, cell_text, 1, 0, "C")
        pdf.ln()
    return bytes(pdf.output())

@st.cache_data(ttl=60)
def load_data(username):
    cols = ["Tanggal"] + list(HABITS.keys()) + EXTRA_COLS
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_excel(DB_FILE, sheet_name=username)
        if not df.empty and 'Tanggal' in df.columns:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
            df.dropna(subset=['Tanggal'], inplace=True)
            for col in cols:
                if col not in df.columns: df[col] = 0 if col != 'Catatan' else ''
            df['Catatan'] = df['Catatan'].fillna('')
        return df
    except (ValueError, FileNotFoundError):
        return pd.DataFrame(columns=cols)

@st.cache_data(ttl=60)
def load_all_user_data(db_file):
    if not os.path.exists(db_file): return pd.DataFrame()
    xls = pd.ExcelFile(db_file)
    all_data = []
    for name in xls.sheet_names:
        if name in PARTICIPANTS:
            try:
                df_user = pd.read_excel(xls, sheet_name=name).assign(User=name)
                all_data.append(df_user)
            except Exception: continue
    if not all_data: return pd.DataFrame()
    master_df = pd.concat(all_data, ignore_index=True)
    if 'Tanggal' in master_df.columns:
        master_df['Tanggal'] = pd.to_datetime(master_df['Tanggal'], errors='coerce').dropna()
    return master_df

def save_data(df, username):
    df_to_save = df.copy()
    if not df_to_save.empty:
        df_to_save['Tanggal'] = pd.to_datetime(df_to_save['Tanggal']).dt.strftime('%Y-%m-%d')
    mode = 'a' if os.path.exists(DB_FILE) else 'w'
    with pd.ExcelWriter(DB_FILE, mode=mode, engine='openpyxl', if_sheet_exists='replace' if mode == 'a' else None) as writer:
        df_to_save.to_excel(writer, sheet_name=username, index=False)

def display_progress_charts(df_period, period_title="", target_days=7):
    st.header(f"Visualisasi Progress {period_title}")
    if df_period.empty:
        st.info("Tidak ada data untuk periode ini.")
        return

    progress_data, total_actual = [], df_period[list(HABITS.keys())].sum().sum()
    total_target = 0

    for habit, type in HABITS.items():
        actual = df_period[habit].sum()
        target = 0
        if type == 'daily': target = target_days
        elif type == 'weekly': target = TARGETS[habit] * (target_days / 7)
        elif type == 'monthly': target = TARGETS[habit] * (target_days / 30)
        
        total_target += target
        percentage = (actual / target * 100) if target > 0 else 0
        progress_data.append({"Ibadah": habit, "Capaian (%)": percentage})

    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("Capaian per Ibadah (%)")
        df_progress = pd.DataFrame(progress_data)
        fig_bar = px.bar(df_progress, x="Capaian (%)", y="Ibadah", orientation='h', text="Capaian (%)", color="Capaian (%)", color_continuous_scale=px.colors.sequential.Greens)
        fig_bar.update_traces(texttemplate='%{x:.0f}%')
        fig_bar.update_layout(xaxis_range=[0, 100], yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{period_title}")
    with col2:
        st.subheader("Progress Keseluruhan")
        remaining = max(0, total_target - total_actual)
        pie_fig = px.pie(pd.DataFrame({"Status": ["Selesai", "Belum"], "Jumlah": [total_actual, remaining]}), values="Jumlah", names="Status", hole=0.4, color_discrete_map={"Selesai": "green", "Belum": "lightgray"})
        st.plotly_chart(pie_fig, use_container_width=True, key=f"pie_{period_title}")

# --- UI UTAMA ---
st.title("🕌 LetsTracker - Habit Tracker Ibadah")

if 'edit_date' not in st.session_state: st.session_state.edit_date = None
if 'confirm_delete_date' not in st.session_state: st.session_state.confirm_delete_date = None

# Sidebar
with st.sidebar:
    st.header("👤 Pengguna")
    username = st.selectbox("Pilih Nama Peserta", options=PARTICIPANTS)
    st.header("🗓️ Pilih Tanggal Input")
    selected_date_input = st.date_input("Pilih tanggal untuk diisi", value=datetime.now().date())

# Memuat data
df = load_data(username)

# Navigasi Utama
main_tabs = st.tabs(["📝 Input Jurnal", "📊 Laporan & Progress", "⚙️ Manajemen Data", "📥 Unduh Laporan"])

# ================================= TAB 1: INPUT JURNAL =================================
with main_tabs[0]:
    st.header(f"Input Jurnal untuk: {selected_date_input.strftime('%A, %d %B %Y')}")
    date_str = selected_date_input.strftime('%Y-%m-%d')
    
    existing_data = None
    if not df.empty:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'])
        if pd.to_datetime(date_str) in df['Tanggal'].values:
            existing_data = df[df['Tanggal'] == pd.to_datetime(date_str)].iloc[0].to_dict()
            st.warning("⚠️ Data untuk tanggal ini sudah ada. Menyimpan lagi akan menimpanya.")
    
    daily_data = existing_data if existing_data else {habit: False for habit in HABITS}
    
    with st.form(key="daily_journal_form"):
        st.subheader("Ibadah")
        cols = st.columns(2)
        for i, (habit, _) in enumerate(HABITS.items()):
            daily_data[habit] = cols[i % 2].checkbox(habit, value=bool(daily_data.get(habit, 0)))
        
        st.subheader("Catatan Harian")
        daily_data['Catatan'] = st.text_area("Tambahkan catatan (opsional)...", value=daily_data.get('Catatan', ''))
        submitted = st.form_submit_button("✅ Simpan Jurnal")

    if submitted:
        new_row_data = {"Tanggal": pd.to_datetime(date_str)}
        for habit in HABITS: new_row_data[habit] = 1 if daily_data.get(habit, False) else 0
        new_row_data['Catatan'] = daily_data.get('Catatan', '')
        
        if existing_data:
            idx = df[df['Tanggal'] == new_row_data['Tanggal']].index
            for col, value in new_row_data.items(): df.loc[idx, col] = value
        else:
            df = pd.concat([df, pd.DataFrame([new_row_data])], ignore_index=True)

        save_data(df.sort_values(by="Tanggal").reset_index(drop=True), username)
        st.success("✨ Jurnal berhasil disimpan!")
        st.cache_data.clear()
        st.rerun()

# ================================= TAB 2: LAPORAN & PROGRESS =================================
with main_tabs[1]:
    st.header(f"Laporan & Progress untuk {username}")
    
    st.subheader("🔥 Runtutan (Streak) Ibadah Harian")
    streaks = calculate_streaks(df)
    if streaks:
        daily_habit_names = [k for k, v in HABITS.items() if v == 'daily']
        streak_cols = st.columns(len(daily_habit_names))
        for i, habit in enumerate(daily_habit_names):
            streak_cols[i].metric(habit, f"{streaks.get(habit, 0)} hari")
    st.markdown("---")

    report_tabs = st.tabs(["Pekan Ini", "Bulan Ini", "🏆 Leaderboard", "Analisis Kustom"])
    today = datetime.now().date()

    with report_tabs[0]:
        start_of_week = today - timedelta(days=today.weekday())
        display_progress_charts(df[df['Tanggal'].dt.date >= start_of_week], "Pekan Ini", target_days=7)
    
    with report_tabs[1]:
        start_of_month = today.replace(day=1)
        days_in_month = (start_of_month.replace(month=start_of_month.month % 12 + 1, day=1) - timedelta(days=1)).day
        display_progress_charts(df[df['Tanggal'].dt.date >= start_of_month], "Bulan Ini", target_days=days_in_month)

    with report_tabs[2]:
        st.header("🏆 Papan Peringkat Peserta")
        all_users_df = load_all_user_data(DB_FILE)
        if all_users_df.empty:
            st.warning("Belum ada data dari peserta manapun untuk ditampilkan.")
        else:
            all_users_df['Tanggal'] = pd.to_datetime(all_users_df['Tanggal'], errors='coerce')
            st.subheader("Peringkat Pekan Ini")
            start_of_week = today - timedelta(days=today.weekday())
            weekly_data_all = all_users_df[all_users_df['Tanggal'].dt.date >= start_of_week]
            
            leaderboard_weekly = []
            if not weekly_data_all.empty:
                for user, group in weekly_data_all.groupby('User'):
                    total_actual, total_target = group[list(HABITS.keys())].sum().sum(), sum(TARGETS.get(h, 7) for h, t in HABITS.items() if t != 'monthly')
                    percentage = (total_actual / total_target * 100) if total_target > 0 else 0
                    leaderboard_weekly.append({"Peserta": user, "Progress (%)": round(percentage, 2)})
                lb_df_w = pd.DataFrame(leaderboard_weekly).sort_values("Progress (%)", ascending=False).reset_index(drop=True)
                lb_df_w.index += 1
                st.dataframe(lb_df_w, use_container_width=True)
            else: st.info("Belum ada data pekan ini untuk leaderboard.")
            
    with report_tabs[3]: 
        st.subheader("Analisis Rentang Tanggal Kustom")
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Tanggal Mulai", today.replace(day=1))
        end_date = col2.date_input("Tanggal Akhir", today)

        if start_date > end_date:
            st.error("Tanggal Mulai tidak boleh melebihi Tanggal Akhir.")
        else:
            filtered_df = df[(df['Tanggal'].dt.date >= start_date) & (df['Tanggal'].dt.date <= end_date)]
            delta_days = (end_date - start_date).days + 1
            display_progress_charts(filtered_df, f"Kustom", target_days=delta_days)

# ================================= TAB 3: MANAJEMEN DATA =================================
with main_tabs[2]:
    st.header(f"Manajemen Data Jurnal - {username}")

    if st.session_state.edit_date is not None:
        edit_date_obj = st.session_state.edit_date
        st.subheader(f"Mengedit Jurnal untuk: {edit_date_obj.strftime('%A, %d %B %Y')}")
        data_to_edit = df[df['Tanggal'] == edit_date_obj].iloc[0].to_dict()
        with st.form(key="edit_form"):
            for i, (habit, _) in enumerate(HABITS.items()):
                data_to_edit[habit] = st.checkbox(habit, value=bool(data_to_edit.get(habit, 0)))
            data_to_edit['Catatan'] = st.text_area("Catatan", value=data_to_edit.get('Catatan', ''))
            
            c1,c2 = st.columns(2)
            if c1.form_submit_button("💾 Simpan Perubahan", use_container_width=True, type="primary"):
                idx = df[df['Tanggal'] == edit_date_obj].index
                for col, value in data_to_edit.items(): df.loc[idx, col] = value
                save_data(df, username)
                st.success("✨ Perubahan berhasil disimpan!")
                st.session_state.edit_date = None
                st.cache_data.clear()
                st.rerun()
            if c2.form_submit_button("❌ Batal", use_container_width=True):
                st.session_state.edit_date = None
                st.rerun()

    elif st.session_state.confirm_delete_date is not None:
        confirm_date_obj = st.session_state.confirm_delete_date
        st.warning(f"**Konfirmasi Hapus**: Yakin ingin menghapus data tanggal **{confirm_date_obj.strftime('%d %B %Y')}**?")
        c1, c2, _ = st.columns([1,1,4])
        if c1.button("✅ Ya, Hapus", type="primary"):
            df = df[df['Tanggal'] != confirm_date_obj]
            save_data(df, username)
            st.session_state.confirm_delete_date = None
            st.cache_data.clear()
            st.success("Data berhasil dihapus.")
            st.rerun()
        if c2.button("❌ Batal"):
            st.session_state.confirm_delete_date = None
            st.rerun()
            
    else:
        st.subheader("Daftar Jurnal Tersimpan")
        if not df.empty:
            for _, row in df.sort_values(by="Tanggal", ascending=False).iterrows():
                with st.expander(f"**{row['Tanggal'].strftime('%A, %d %B %Y')}**"):
                    for habit in HABITS.keys():
                        st.markdown(f"- **{habit}**: {'✅' if row.get(habit, 0) == 1 else '❌'}")
                    if pd.notna(row.get('Catatan')) and row.get('Catatan'):
                        st.info(f"**Catatan**: {row['Catatan']}")
                    
                    c1, c2 = st.columns([1,1])
                    if c1.button("✏️ Edit", key=f"edit_{row['Tanggal']}", use_container_width=True):
                        st.session_state.edit_date = row['Tanggal']
                        st.rerun()
                    if c2.button("🗑️ Hapus", key=f"del_{row['Tanggal']}", use_container_width=True):
                        st.session_state.confirm_delete_date = row['Tanggal']
                        st.rerun()
        else:
            st.warning("Belum ada data jurnal untuk dikelola.")

# ================================= TAB 4: UNDUH LAPORAN =================================
with main_tabs[3]:
    st.header(f"Unduh Laporan Progress - {username}")
    if df.empty:
        st.warning("Tidak ada data untuk diunduh.")
    else:
        st.dataframe(df.sort_values("Tanggal", ascending=False))
        c1, c2 = st.columns(2)
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'Progress_{username}')
        c1.download_button("📥 Unduh Semua Data (Excel)", output_excel.getvalue(), f"semua_progress_{username}.xlsx", use_container_width=True)

        pdf_data = df_to_pdf(df, f"Laporan Lengkap - {username}")
        c2.download_button("📄 Unduh Semua Data (PDF)", pdf_data, f"semua_progress_{username}.pdf", use_container_width=True)