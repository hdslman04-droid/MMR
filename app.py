import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
from PIL import Image, ImageDraw

st.set_page_config(
    page_title="MMR KPA (GAJI)",
    page_icon="TDM.png",
    layout="centered",
    initial_sidebar_state="expanded"
)

if "host_logged_in" not in st.session_state:
    st.session_state.host_logged_in = False

st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 900px;
}

.time-box {
    text-align: center;
    font-size: 16px;
    font-weight: 600;
    padding: 10px;
    border-radius: 10px;
    background-color: #f3f4f6;
    margin-top: 14px;
    margin-bottom: 18px;
    color: black;
}

.center-caption {
    text-align: center;
    margin-bottom: 20px;
    color: #555;
}

div[data-testid="stTextInput"] {
    max-width: 420px;
}

@media (max-width: 640px) {
    .block-container {
        padding-top: 0.5rem;
        padding-left: 0.7rem;
        padding-right: 0.7rem;
    }
}
</style>
""", unsafe_allow_html=True)


DATA_FILE = "SEATING PLAN MMR PENGHARGAAN 2026 2.csv"
ATTENDANCE_FILE = "attendance_records.csv"

LOGO_UGAT = "Logo-UGAT.png"
CENTER_IMAGE = "LAYOUT SUSUNAN.png"

DEFAULT_HOST_PASSWORD = "host123"

required_cols = ["BIL", "NOTEN", "NAMA", "MENU", "MEJA"]


# =========================================================
# BASIC FUNCTIONS
# =========================================================
def get_file_mtime(file_path):
    path = Path(file_path)

    if path.exists():
        return path.stat().st_mtime

    return 0


def get_file_updated_time():
    files_to_check = [DATA_FILE, ATTENDANCE_FILE]
    existing_files = [Path(f) for f in files_to_check if Path(f).exists()]

    if not existing_files:
        return "Tiada rekod"

    latest_file = max(existing_files, key=lambda x: x.stat().st_mtime)
    latest_time = datetime.fromtimestamp(
        latest_file.stat().st_mtime,
        ZoneInfo("Asia/Kuala_Lumpur")
    )

    return latest_time.strftime("%d/%m/%Y %I:%M:%S %p")


def clean_csv(df_raw):
    df_raw = df_raw.dropna(how="all").reset_index(drop=True)

    # Bersihkan column sedia ada
    df_raw.columns = [str(col).strip().upper() for col in df_raw.columns]

    # Jika CSV memang sudah ada header yang betul
    if all(col in df_raw.columns for col in required_cols):
        df = df_raw.copy()

    else:
        header_row_index = None

        # Cari row sebenar yang mengandungi BIL, NOTEN, NAMA, MENU, MEJA
        for i in range(len(df_raw)):
            row_values = [
                str(value).strip().upper()
                for value in df_raw.iloc[i].tolist()
            ]

            if (
                "BIL" in row_values
                and "NOTEN" in row_values
                and "NAMA" in row_values
                and "MENU" in row_values
                and "MEJA" in row_values
            ):
                header_row_index = i
                break

        if header_row_index is None:
            st.error(
                "Header CSV tidak dijumpai. Pastikan fail CSV ada kolum "
                "BIL, NOTEN, NAMA, MENU dan MEJA."
            )
            st.stop()

        headers = [
            str(value).strip().upper()
            for value in df_raw.iloc[header_row_index].tolist()
        ]

        df = df_raw.iloc[header_row_index + 1:].copy()
        df.columns = headers

    # Buang column kosong / unnamed
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, [str(col).strip() != "" for col in df.columns]]
    df = df.loc[:, ~df.columns.astype(str).str.upper().str.startswith("UNNAMED")]

    # Bersihkan data
    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = [str(col).strip().upper() for col in df.columns]

    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Buang .0 jika Excel convert nombor kepada decimal
    if "BIL" in df.columns:
        df["BIL"] = df["BIL"].str.replace(".0", "", regex=False)

    if "NOTEN" in df.columns:
        df["NOTEN"] = df["NOTEN"].str.replace(".0", "", regex=False)

    if "MEJA" in df.columns:
        df["MEJA"] = df["MEJA"].str.upper().str.replace(".0", "", regex=False)

    return df


@st.cache_data
def load_default_data(file_mtime):
    file_path = Path(DATA_FILE)

    if not file_path.exists():
        st.error(f"Fail '{DATA_FILE}' tidak dijumpai.")
        st.stop()

    df_raw = pd.read_csv(file_path, encoding="utf-8")
    return clean_csv(df_raw)


def load_uploaded_files(uploaded_files):
    all_data = []

    for uploaded_file in uploaded_files:
        df_raw = pd.read_csv(uploaded_file, encoding="utf-8")
        df = clean_csv(df_raw)
        all_data.append(df)

    if not all_data:
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)


def load_attendance():
    file_path = Path(ATTENDANCE_FILE)

    if file_path.exists():
        try:
            attendance_df = pd.read_csv(file_path)
            attendance_df.columns = [str(col).strip().upper() for col in attendance_df.columns]

            for col in attendance_df.columns:
                attendance_df[col] = attendance_df[col].fillna("").astype(str).str.strip()

            if "NOTEN" in attendance_df.columns:
                attendance_df["NOTEN"] = attendance_df["NOTEN"].str.replace(".0", "", regex=False)

            return attendance_df
        except Exception:
            pass

    return pd.DataFrame(columns=[
        "BIL", "NOTEN", "NAMA", "MENU", "MEJA",
        "STATUS_KEHADIRAN", "TARIKH_MASA"
    ])


def save_attendance(attendance_df):
    attendance_df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8")


def reset_attendance():
    reset_attendance_df = pd.DataFrame(columns=[
        "BIL", "NOTEN", "NAMA", "MENU", "MEJA",
        "STATUS_KEHADIRAN", "TARIKH_MASA"
    ])

    reset_attendance_df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8")


def show_image_if_exists(image_path, width=None, use_container_width=False):
    path = Path(image_path)

    if path.exists():
        st.image(str(path), width=width, use_container_width=use_container_width)


def verify_host_password(password_input):
    try:
        real_password = st.secrets["HOST_PASSWORD"]
    except Exception:
        real_password = DEFAULT_HOST_PASSWORD

    return password_input == real_password


def get_base64_image(image_path):
    path = Path(image_path)

    if not path.exists():
        return ""

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# =========================================================
# HIGHLIGHT MEJA DALAM LAYOUT
# =========================================================
def generate_seat_map():
    seat_map = {}

    row_y = {
        "FL": 28,
        "FR": 84,
        "EL": 112,
        "ER": 168,
        "DL": 196,
        "DR": 252,
        "CL": 308,
        "CR": 364,
        "BL": 392,
        "BR": 448,
        "AL": 476,
        "AR": 532,
    }

    start_x = 70
    gap_x = 50

    for prefix, y in row_y.items():
        for seat_no in range(20, 0, -1):
            x = start_x + (20 - seat_no) * gap_x
            seat_id = f"{prefix}{seat_no}"

            seat_map[seat_id] = {
                "x": x,
                "y": y,
                "w": 30,
                "h": 18
            }

    right_side_positions = {
        "18": (1155, 42),
        "16": (1155, 70),
        "14": (1155, 98),
        "12": (1155, 126),
        "10": (1155, 154),
        "8": (1155, 182),
        "6": (1155, 210),
        "4": (1155, 238),
        "2": (1155, 266),
        "1": (1155, 294),
        "3": (1155, 322),
        "5": (1155, 350),
        "7": (1155, 378),
        "9": (1155, 406),
        "11": (1155, 434),
        "13": (1155, 462),
        "15": (1155, 490),
        "17": (1155, 518),
    }

    for meja, (x, y) in right_side_positions.items():
        seat_map[meja] = {
            "x": x,
            "y": y,
            "w": 24,
            "h": 18
        }

    return seat_map


def show_highlighted_layout(image_path, group_df):
    path = Path(image_path)

    if not path.exists():
        st.warning(f"Fail gambar '{image_path}' tidak dijumpai.")
        return

    image = Image.open(path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    seat_map = generate_seat_map()

    meja_list = (
        group_df["MEJA"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
    )

    missing_meja = []

    for meja in meja_list:
        if meja in seat_map:
            info = seat_map[meja]

            x = info["x"]
            y = info["y"]
            w = info["w"]
            h = info["h"]

            fill_color = (255, 0, 0, 90)
            outline_color = (255, 0, 0, 255)

            draw.rectangle(
                [x - w // 2, y - h // 2, x + w // 2, y + h // 2],
                fill=fill_color,
                outline=outline_color,
                width=4
            )
        else:
            missing_meja.append(meja)

    highlighted_image = Image.alpha_composite(image, overlay)
    st.image(highlighted_image, use_container_width=True)

    if missing_meja:
        st.warning(f"Meja ini belum ada coordinate dalam layout: {', '.join(missing_meja)}")


# =========================================================
# SIDEBAR HOST LOGIN + UPLOAD
# =========================================================
if st.session_state.host_logged_in:
    st.sidebar.title("Host Panel")
    st.sidebar.success("Anda login sebagai host.")

    uploaded_files = st.sidebar.file_uploader(
        "Upload CSV Files",
        accept_multiple_files=True,
        type=["csv"]
    )

    if uploaded_files:
        try:
            new_df = load_uploaded_files(uploaded_files)

            missing_uploaded_cols = [
                col for col in required_cols
                if col not in new_df.columns
            ]

            if missing_uploaded_cols:
                st.sidebar.error(
                    f"CSV baru tidak lengkap. Kolum tiada: {missing_uploaded_cols}"
                )
            else:
                # Simpan CSV baru sebagai data utama untuk semua user
                new_df.to_csv(DATA_FILE, index=False, encoding="utf-8")

                # Reset kehadiran bila data baru upload
                reset_attendance()

                # Clear cache supaya data lama tidak digunakan
                st.cache_data.clear()

                st.sidebar.success(
                    "CSV baru berjaya dimuat naik. "
                    "Data tetamu telah dikemaskini dan rekod kehadiran telah direset."
                )

                st.rerun()

        except Exception as e:
            st.sidebar.error(f"Fail tidak dapat dibaca: {e}")

    if st.sidebar.button("Logout Host"):
        st.session_state.host_logged_in = False
        st.rerun()

else:
    st.sidebar.title("Host Login")

    host_password_input = st.sidebar.text_input(
        "Masukkan kata laluan",
        type="password"
    )

    if st.sidebar.button("Login"):
        if verify_host_password(host_password_input):
            st.session_state.host_logged_in = True
            st.sidebar.success("Login berjaya.")
            st.rerun()
        else:
            st.sidebar.error("Kata laluan salah.")


# =========================================================
# LOAD DATA
# Semua user akan baca DATA_FILE utama, bukan session host
# =========================================================
df = load_default_data(get_file_mtime(DATA_FILE))
attendance_df = load_attendance()

missing_cols = [col for col in required_cols if col not in df.columns]

if missing_cols:
    st.error(f"Kolum berikut tiada dalam fail CSV: {missing_cols}")
    st.stop()


# =========================================================
# BANNER HEADER
# =========================================================
img_base64 = get_base64_image(LOGO_UGAT)

if img_base64:
    st.markdown(f"""
    <div style="
        display:flex;
        align-items:center;
        gap:12px;
        background: linear-gradient(90deg, #020617, #111827);
        padding:15px;
        border-radius:15px;
        margin-bottom:15px;
    ">
        <img src="data:image/png;base64,{img_base64}" width="50">
        <h2 style="margin:0; color:white;">
            Sistem Kehadiran Majlis Makan Malam Regimental KPA (GAJI)
        </h2>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="
        display:flex;
        align-items:center;
        gap:12px;
        background: linear-gradient(90deg, #020617, #111827);
        padding:15px;
        border-radius:15px;
        margin-bottom:15px;
    ">
        <h2 style="margin:0; color:white;">
            Sistem Kehadiran Majlis Makan Malam Regimental KPA (GAJI)
        </h2>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# SEARCH SECTION
# =========================================================
st.markdown(
    "<h3 style='color:#38bdf8;'>Carian Nombor Tentera</h3>",
    unsafe_allow_html=True
)

search_no = st.text_input(
    "Masukkan No Tentera",
    max_chars=10,
    placeholder="Contoh: 3004463"
)

if search_no:
    search_value = search_no.strip()

    result_df = df[
        df["NOTEN"].astype(str).str.contains(search_value, case=False, na=False)
    ].copy()

    if result_df.empty:
        st.warning("Tiada rekod dijumpai untuk nombor tentera tersebut.")
    else:
        bil_value = str(result_df.iloc[0]["BIL"]).strip()
        group_df = df[df["BIL"].astype(str).str.strip() == bil_value].copy()

        st.success(f"Rekod dijumpai. BIL: {bil_value}")

        st.markdown("### Maklumat Kehadiran")

        display_cols = ["BIL", "NOTEN", "NAMA", "MENU", "MEJA"]

        if "CATATAN" in group_df.columns:
            display_cols.append("CATATAN")

        st.table(group_df[display_cols])

        st.markdown("### Pelan Kedudukan Dewan")
        show_highlighted_layout(CENTER_IMAGE, group_df)

        st.markdown(
            f"<div class='time-box'>Last Updated: {get_file_updated_time()}</div>",
            unsafe_allow_html=True
        )

        sudah_hadir_semua = True

        for idx, row in group_df.iterrows():
            noten = str(row["NOTEN"]).strip()

            sudah_hadir = False

            if not attendance_df.empty and "NOTEN" in attendance_df.columns:
                sudah_hadir = noten in attendance_df["NOTEN"].astype(str).str.strip().values

            if not sudah_hadir:
                sudah_hadir_semua = False

        if sudah_hadir_semua:
            st.success("✅ TELAH HADIR")
        else:
            st.warning("❌ BELUM HADIR")

        if st.session_state.host_logged_in:
            if not sudah_hadir_semua:
                if st.button("Submit / Tandakan Kehadiran Kumpulan Ini"):

                    new_records = []

                    for idx, row in group_df.iterrows():
                        noten = str(row["NOTEN"]).strip()

                        already_exists = False

                        if not attendance_df.empty and "NOTEN" in attendance_df.columns:
                            already_exists = noten in attendance_df["NOTEN"].astype(str).str.strip().values

                        if not already_exists:
                            new_records.append({
                                "BIL": row["BIL"],
                                "NOTEN": row["NOTEN"],
                                "NAMA": row["NAMA"],
                                "MENU": row["MENU"],
                                "MEJA": row["MEJA"],
                                "STATUS_KEHADIRAN": "HADIR",
                                "TARIKH_MASA": datetime.now(
                                    ZoneInfo("Asia/Kuala_Lumpur")
                                ).strftime("%Y-%m-%d %H:%M:%S")
                            })

                    if new_records:
                        attendance_df = pd.concat(
                            [attendance_df, pd.DataFrame(new_records)],
                            ignore_index=True
                        )
                        save_attendance(attendance_df)
                        st.success("Kehadiran berjaya direkodkan.")
                        st.rerun()
                    else:
                        st.info("Semua dalam BIL ini telah ditandakan hadir.")
        else:
            st.info("Hanya host boleh tandakan kehadiran.")

else:
    st.info("Sila masukkan No Tentera untuk membuat carian.")

st.markdown("---")


# =========================================================
# LIVE ATTENDANCE - HOST ONLY
# =========================================================
if st.session_state.host_logged_in:
    st.markdown("### 📋 Live Attendance / Kehadiran Semasa")

    hadir_noten = []

    if not attendance_df.empty and "NOTEN" in attendance_df.columns:
        hadir_noten = attendance_df["NOTEN"].astype(str).str.strip().tolist()

    belum_hadir_df = df[
        ~df["NOTEN"].astype(str).str.strip().isin(hadir_noten)
    ].copy()

    total_semua = len(df)
    total_hadir = len(attendance_df)
    total_belum_hadir = len(belum_hadir_df)

    st.info(f"Jumlah Keseluruhan: {total_semua}")
    st.success(f"Jumlah Telah Hadir: {total_hadir}")
    st.warning(f"Jumlah Belum Hadir: {total_belum_hadir}")

    st.markdown("### ✅ Telah Hadir")

    if attendance_df.empty:
        st.warning("Belum ada rekod kehadiran.")
    else:
        st.dataframe(attendance_df, use_container_width=True)

    st.markdown("### ❌ Belum Hadir")

    if belum_hadir_df.empty:
        st.success("Semua telah hadir.")
    else:
        belum_cols = ["BIL", "NOTEN", "NAMA", "MENU", "MEJA"]

        if "CATATAN" in belum_hadir_df.columns:
            belum_cols.append("CATATAN")

        st.dataframe(belum_hadir_df[belum_cols], use_container_width=True)

    csv_data = attendance_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Muat Turun Rekod Kehadiran",
        data=csv_data,
        file_name="attendance_records.csv",
        mime="text/csv"
    )
