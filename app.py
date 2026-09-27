"""
Aplikasi Kalibrasi & Pengukuran Dimensi (berbasis Streamlit)
=============================================================
Mereplikasi perhitungan pada file Excel:
 - Sheet "General"    -> kalibrasi alat ukur terhadap gauge block,
                          menghasilkan Systematic Error (interpolasi linear).
 - Sheet "Pengukuran" -> statistik pengukuran per anggota + data
                          keseluruhan (Mean, Median, Range, Std Dev, CV,
                          Standard Error of Mean, Combined Error,
                          Expanded Uncertainty (k=2), Confidence Interval
                          95% (distribusi-t dua sisi), dan Final Result).

Jalankan dengan:
    pip install -r requirements.txt
    streamlit run app.py
"""

import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

st.set_page_config(page_title="Kalibrasi & Pengukuran", page_icon="📏", layout="wide")

st.title("📏 Aplikasi Kalibrasi & Pengukuran Dimensi")
st.caption(
    "Replika perhitungan proyek pengukuran teknik (kalibrasi gauge block + "
    "statistik pengukuran berulang), sesuai logika pada file Excel sumber."
)

# ----------------------------------------------------------------------
# SIDEBAR — Info umum proyek
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("ℹ️ Info Proyek")
    benda_kerja = st.text_input("Benda kerja", "Seher (Piston) Yamaha Vixion NVL")
    dimensi = st.text_input("Dimensi yang diukur", "Diameter piston")
    alat_ukur = st.text_input("Alat ukur", "Vernier caliper (Jangka sorong)")
    merk = st.text_input("Merk", "Mitutoyo")
    ketelitian = st.text_input("Ketelitian", "0.02 mm")
    range_alat = st.text_input("Range alat", "300 mm")
    suhu = st.text_input("Suhu pre-conditioning", "20°C")
    st.divider()
    ukuran_acuan = st.number_input("Ukuran Acuan / nominal benda kerja (mm)", value=57.0, step=0.01, format="%.2f")
    st.caption(
        "Systematic Error dihitung dengan interpolasi linear dari deviasi "
        "kalibrasi gauge block pada Ukuran Acuan ini."
    )

# ----------------------------------------------------------------------
# 1) KALIBRASI (sheet "General")
# ----------------------------------------------------------------------
st.header("1️⃣ Kalibrasi Alat Ukur (Gauge Block)")
st.write(
    "Masukkan hasil pengukuran beberapa gauge block (idealnya mencakup nilai "
    "di bawah & di atas Ukuran Acuan) untuk menghitung deviasi alat ukur."
)

if "calib_df" not in st.session_state:
    st.session_state.calib_df = pd.DataFrame(
        {
            "Uk. Gauge Block": [10.0, 50.0, 60.0],
            "Pengukuran 1": [9.90, 49.88, 59.86],
            "Pengukuran 2": [9.88, 49.86, 59.84],
            "Pengukuran 3": [9.90, 49.90, 59.88],
        }
    )

calib_input = st.data_editor(
    st.session_state.calib_df,
    num_rows="dynamic",
    use_container_width=True,
    key="calib_editor",
)
st.session_state.calib_df = calib_input

calib_df = calib_input.dropna(subset=["Uk. Gauge Block"]).copy()
meas_cols_calib = [c for c in calib_df.columns if c.startswith("Pengukuran")]

if len(calib_df) >= 2 and len(meas_cols_calib) >= 1:
    calib_df["Mean"] = calib_df[meas_cols_calib].mean(axis=1)
    calib_df["Mean Deviation"] = (calib_df["Uk. Gauge Block"] - calib_df["Mean"]).abs()

    st.dataframe(calib_df.style.format(precision=4), use_container_width=True)

    calib_sorted = calib_df.sort_values("Uk. Gauge Block").reset_index(drop=True)

    def interpolate_deviation(df: pd.DataFrame, x: float) -> float:
        xs = df["Uk. Gauge Block"].to_numpy()
        ys = df["Mean Deviation"].to_numpy()
        if x <= xs[0]:
            i0, i1 = 0, 1
        elif x >= xs[-1]:
            i0, i1 = len(xs) - 2, len(xs) - 1
        else:
            i1 = int(np.searchsorted(xs, x))
            i0 = i1 - 1
        x0, x1 = xs[i0], xs[i1]
        y0, y1 = ys[i0], ys[i1]
        if x1 == x0:
            return float(y0)
        return float(y0 + (y1 - y0) * (x - x0) / (x1 - x0))

    systematic_error = interpolate_deviation(calib_sorted, ukuran_acuan)
else:
    systematic_error = 0.0
    st.warning("Minimal 2 baris gauge block diperlukan untuk interpolasi.")

c1, c2 = st.columns(2)
c1.metric("Systematic Error (interpolasi @ Ukuran Acuan)", f"{systematic_error:.4f} mm")
c2.info(f"**Hasil Deviasi:** -{systematic_error:.2f} mm")

if len(calib_df) >= 2 and len(meas_cols_calib) >= 1:
    st.subheader("📈 Grafik Kalibrasi")
    fig_cal, ax_cal = plt.subplots(figsize=(7, 4))
    ax_cal.plot(calib_sorted["Uk. Gauge Block"], calib_sorted["Mean Deviation"], "o-", color="tab:blue", label="Deviasi hasil kalibrasi")
    ax_cal.axvline(ukuran_acuan, color="gray", linestyle="--", alpha=0.6)
    ax_cal.scatter([ukuran_acuan], [systematic_error], color="red", zorder=5, label=f"Systematic Error @ {ukuran_acuan:g} mm")
    ax_cal.set_xlabel("Uk. Gauge Block (mm)")
    ax_cal.set_ylabel("Mean Deviation (mm)")
    ax_cal.set_title("Deviasi Kalibrasi vs Ukuran Gauge Block")
    ax_cal.legend()
    ax_cal.grid(alpha=0.3)
    st.pyplot(fig_cal)
    plt.close(fig_cal)

st.divider()

# ----------------------------------------------------------------------
# 2) DATA PENGUKURAN (sheet "Pengukuran")
# ----------------------------------------------------------------------
st.header("2️⃣ Data Pengukuran per Anggota")

n_cols = st.number_input("Jumlah pengulangan pengukuran per anggota", min_value=2, max_value=10, value=5, key="n_cols")


def build_default_meas(n: int) -> pd.DataFrame:
    cols = [f"Pengukuran {i + 1}" for i in range(n)]
    data = {"Nama Anggota": ["Anggota 1", "Anggota 2", "Anggota 3"]}
    for c in cols:
        data[c] = [56.86, 56.88, 56.84]
    return pd.DataFrame(data)


current_cols = [c for c in st.session_state.get("meas_df", pd.DataFrame()).columns if c.startswith("Pengukuran")]
if "meas_df" not in st.session_state or len(current_cols) != n_cols:
    st.session_state.meas_df = build_default_meas(n_cols)

meas_input = st.data_editor(
    st.session_state.meas_df,
    num_rows="dynamic",
    use_container_width=True,
    key="meas_editor",
)
st.session_state.meas_df = meas_input

meas_df = meas_input.dropna(subset=["Nama Anggota"]).copy()
meas_cols = [c for c in meas_df.columns if c.startswith("Pengukuran")]
n = len(meas_cols)

if len(meas_df) >= 1 and n >= 2:
    t_row = stats.t.ppf(1 - 0.05 / 2, n - 1)

    rows = []
    for _, row in meas_df.iterrows():
        vals = row[meas_cols].astype(float).to_numpy()
        mean = float(np.mean(vals))
        median = float(np.median(vals))
        rng = float(vals.max() - vals.min())
        sd = float(np.std(vals, ddof=1))
        cv = sd / mean if mean else 0.0
        sem = sd / np.sqrt(n)
        combined = float(np.sqrt(systematic_error**2 + sem**2))
        expanded = combined * 2
        ci = t_row * sem
        final = mean + systematic_error
        rows.append(
            {
                "Nama Anggota": row["Nama Anggota"],
                "Mean": mean,
                "Median": median,
                "Range": rng,
                "Std Dev": sd,
                "CV": cv,
                "Systematic Error": systematic_error,
                "SEM": sem,
                "Combined Error": combined,
                "Expanded Uncertainty (k=2)": expanded,
                "CI 95%": f"{mean:.4f} ± {ci:.4f}",
                "Final Result": f"{final:.4f} ± {expanded:.4f}",
            }
        )
    res_df = pd.DataFrame(rows)

    st.subheader("Hasil per Anggota")
    st.dataframe(res_df.style.format(precision=4, subset=res_df.columns[1:9]), use_container_width=True)

    # ---------------- Overall ----------------
    all_vals = meas_df[meas_cols].astype(float).to_numpy().flatten()
    N = len(all_vals)
    t_overall = stats.t.ppf(1 - 0.05 / 2, N - 1)

    overall_mean = float(np.mean(all_vals))
    overall_sd = float(np.std(all_vals, ddof=1))
    overall_median = float(np.median(all_vals))
    overall_range = float(all_vals.max() - all_vals.min())
    overall_cv = overall_sd / overall_mean if overall_mean else 0.0
    overall_sem = overall_sd / np.sqrt(N)
    overall_combined = float(np.sqrt(systematic_error**2 + overall_sem**2))
    overall_expanded = overall_combined * 2
    overall_ci = t_overall * overall_sem
    overall_final = overall_mean + systematic_error

    st.subheader("Ringkasan Data Keseluruhan (Overall)")
    overall_df = pd.DataFrame(
        {
            "Parameter": [
                "Mean", "Std Dev", "Median", "Range", "Coefficient of Variation",
                "Systematic Error", "Standard Error of the Mean", "Combined Error",
                "Expanded Uncertainty (k=2)", "Confidence Interval (95%)", "Final Result",
            ],
            "Nilai": [
                f"{overall_mean:.4f}", f"{overall_sd:.4f}", f"{overall_median:.4f}",
                f"{overall_range:.4f}", f"{overall_cv:.6f}", f"{systematic_error:.4f}",
                f"{overall_sem:.4f}", f"{overall_combined:.4f}", f"{overall_expanded:.4f}",
                f"{overall_mean:.4f} ± {overall_ci:.4f}", f"{overall_final:.4f} ± {overall_expanded:.4f}",
            ],
        }
    )
    st.table(overall_df)

    m1, m2, m3 = st.columns(3)
    m1.metric("Mean keseluruhan", f"{overall_mean:.4f} mm")
    m2.metric("Std Dev keseluruhan", f"{overall_sd:.4f}")
    m3.metric("Final Result", f"{overall_final:.4f} ± {overall_expanded:.4f} mm")

    # ---------------- Visualisasi ----------------
    st.divider()
    st.header("3️⃣ Visualisasi Data")

    names = res_df["Nama Anggota"]
    means = res_df["Mean"]
    expanded_errs = res_df["Expanded Uncertainty (k=2)"]
    finals = res_df["Mean"] + systematic_error

    # 1) Sebaran data mentah per anggota
    st.subheader("Sebaran Data Pengukuran per Anggota")
    fig_scatter, ax_scatter = plt.subplots(figsize=(8, 4))
    for _, row in meas_df.iterrows():
        vals = row[meas_cols].astype(float).to_numpy()
        ax_scatter.scatter([row["Nama Anggota"]] * len(vals), vals, alpha=0.6, color="tab:blue")
    ax_scatter.set_ylabel("Hasil Pengukuran (mm)")
    ax_scatter.set_title("Titik Data Mentah per Anggota")
    plt.setp(ax_scatter.get_xticklabels(), rotation=30, ha="right")
    ax_scatter.grid(alpha=0.3, axis="y")
    st.pyplot(fig_scatter)
    plt.close(fig_scatter)

    # 2) Run chart / tren tiap pengulangan
    st.subheader("Tren Pengukuran per Pengulangan (Run Chart)")
    fig_run, ax_run = plt.subplots(figsize=(8, 4))
    for _, row in meas_df.iterrows():
        vals = row[meas_cols].astype(float).to_numpy()
        ax_run.plot(range(1, n + 1), vals, marker="o", label=row["Nama Anggota"])
    ax_run.axhline(overall_mean, color="black", linestyle="--", alpha=0.6, label="Overall Mean")
    ax_run.set_xlabel("Pengulangan ke-")
    ax_run.set_ylabel("Nilai Pengukuran (mm)")
    ax_run.set_xticks(range(1, n + 1))
    ax_run.legend(fontsize=8)
    ax_run.grid(alpha=0.3)
    st.pyplot(fig_run)
    plt.close(fig_run)

    # 3) Mean ± Expanded Uncertainty per anggota
    st.subheader("Mean ± Expanded Uncertainty per Anggota")
    fig_err, ax_err = plt.subplots(figsize=(8, 4))
    ax_err.errorbar(names, means, yerr=expanded_errs, fmt="o", capsize=5, color="tab:blue", ecolor="tab:red")
    ax_err.axhline(overall_mean, color="gray", linestyle="--", label=f"Overall Mean ({overall_mean:.3f})")
    ax_err.set_ylabel("Mean ± Expanded Uncertainty (mm)")
    plt.setp(ax_err.get_xticklabels(), rotation=30, ha="right")
    ax_err.legend()
    ax_err.grid(alpha=0.3)
    st.pyplot(fig_err)
    plt.close(fig_err)

    # 4) Final Result per anggota vs Ukuran Acuan
    st.subheader("Final Result per Anggota vs Ukuran Acuan")
    fig_final, ax_final = plt.subplots(figsize=(8, 4))
    ax_final.errorbar(names, finals, yerr=expanded_errs, fmt="s", capsize=5, color="tab:green", ecolor="tab:orange", label="Final Result per Anggota")
    ax_final.axhline(overall_final, color="black", linestyle="--", label=f"Overall Final Result ({overall_final:.3f})")
    ax_final.axhline(ukuran_acuan, color="purple", linestyle=":", label=f"Ukuran Acuan ({ukuran_acuan:g})")
    ax_final.set_ylabel("Final Result (mm)")
    plt.setp(ax_final.get_xticklabels(), rotation=30, ha="right")
    ax_final.legend(fontsize=8)
    ax_final.grid(alpha=0.3)
    st.pyplot(fig_final)
    plt.close(fig_final)

    # 5) Distribusi seluruh data
    st.subheader("Distribusi Seluruh Data Pengukuran")
    fig_hist, ax_hist = plt.subplots(figsize=(8, 4))
    ax_hist.hist(all_vals, bins=min(10, N), color="skyblue", edgecolor="black", alpha=0.85)
    ax_hist.axvline(overall_mean, color="red", linestyle="--", label=f"Mean = {overall_mean:.3f}")
    ax_hist.axvline(overall_mean - overall_sd, color="gray", linestyle=":", label="±1 SD")
    ax_hist.axvline(overall_mean + overall_sd, color="gray", linestyle=":")
    ax_hist.set_xlabel("Nilai Pengukuran (mm)")
    ax_hist.set_ylabel("Frekuensi")
    ax_hist.legend()
    st.pyplot(fig_hist)
    plt.close(fig_hist)

    # ---------------- Export ----------------
    def to_excel_bytes() -> io.BytesIO:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            info_df = pd.DataFrame(
                {
                    "ASPEK": ["Benda kerja", "Dimensi yang diukur", "Alat ukur", "Merk", "Ketelitian", "Range", "Suhu", "Ukuran Acuan"],
                    "KETERANGAN": [benda_kerja, dimensi, alat_ukur, merk, ketelitian, range_alat, suhu, ukuran_acuan],
                }
            )
            info_df.to_excel(writer, sheet_name="General", index=False, startrow=0)
            calib_df.to_excel(writer, sheet_name="General", index=False, startrow=len(info_df) + 3)
            meas_df.to_excel(writer, sheet_name="Pengukuran", index=False, startrow=0)
            res_df.to_excel(writer, sheet_name="Pengukuran", index=False, startrow=len(meas_df) + 3)
            overall_df.to_excel(writer, sheet_name="Pengukuran", index=False, startrow=len(meas_df) + len(res_df) + 6)
        buf.seek(0)
        return buf

    st.download_button(
        "⬇️ Download Hasil (Excel)",
        data=to_excel_bytes(),
        file_name="Hasil_Pengukuran.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.warning("Tambahkan minimal 1 anggota dengan minimal 2 pengulangan pengukuran.")

st.divider()
with st.expander("📝 Catatan metode"):
    st.markdown(
        """
1. **Systematic Error** diambil dari hasil interpolasi linear deviasi kalibrasi (data gauge block) pada *Ukuran Acuan*, lalu dipakai sebagai koreksi pada seluruh perhitungan pengukuran.
2. **Expanded Uncertainty** dihitung dengan faktor cakupan **k = 2** (~95%).
3. **Confidence Interval (95%)** memakai nilai sebaran‑t dua sisi (setara fungsi Excel `TINV`) sesuai derajat kebebasan (n − 1).
4. **Final Result = Mean + Systematic Error**, sebagai koreksi atas alat ukur yang terbukti membaca lebih rendah/tinggi dari ukuran sebenarnya.
        """
    )
