import streamlit as st
import requests
import os
import time

SERVER_URL = os.getenv("SERVER_URL", "http://server:5000")

st.set_page_config(
    page_title="Federated Analytics Dashboard",
    page_icon="🔒",
    layout="wide",
)

st.title("🔒 Privacy-Preserving Federated Analytics Engine")
st.caption("Real-time view of federated nodes and aggregated results")

# ── Sidebar ───────────────────────────────────────────────────────────────────
refresh = st.sidebar.slider("Auto-refresh (seconds)", 5, 60, 5)
st.sidebar.info(f"Refreshing every {refresh}s")


# ── Helpers ───────────────────────────────────────────────────────────────────
def fetch(endpoint: str):
    try:
        r = requests.get(f"{SERVER_URL}{endpoint}", timeout=3)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot reach server — is it running?"}
    except requests.exceptions.Timeout:
        return {"error": "Server timed out"}
    except Exception as e:
        return {"error": str(e)}


def server_unreachable(data) -> bool:
    return isinstance(data, dict) and "error" in data


# ── Server health check ───────────────────────────────────────────────────────
health = fetch("/health")

if server_unreachable(health):
    st.error(f"🔴 Server unreachable: {health['error']}")
    st.info("Make sure the server container is running and try again.")
    time.sleep(refresh)
    st.rerun()

# ── Row 1: Node Health + Server Metrics ──────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("🖥️ Node Health")
    status = fetch("/nodes/status")
    if server_unreachable(status):
        st.error(status["error"])
    elif not status:
        st.info("No nodes registered yet.")
    else:
        for node, state in status.items():
            color = "green" if state == "alive" else "red"
            icon  = "🟢" if state == "alive" else "🔴"
            st.markdown(
                f"<span style='color:{color}'>{icon} **{node}**</span> — `{state}`",
                unsafe_allow_html=True,
            )

with col2:
    st.subheader("❤️ Server Health")
    if server_unreachable(health):
        st.error(health["error"])
    else:
        st.metric("Current Round", health.get("round", 0))
        next_in = health.get("next_aggregation_in")
        if next_in is not None:
            st.metric("Next auto-aggregation", f"{int(next_in)}s")
        st.success("Server is online")

st.divider()

# ── Row 2: Privacy Budget Tracker ────────────────────────────────────────────
st.subheader("🔐 Privacy Budget Tracker")
st.caption("Remaining epsilon budget per node (lower ε = stronger privacy)")

results = fetch("/results")
if server_unreachable(results):
    st.error(results["error"])
else:
    submissions = results.get("submissions", {})
    if not submissions:
        st.info("No submissions yet.")
    else:
        EPSILON_BUDGET = float(os.getenv("EPSILON_BUDGET", "10.0"))
        budget_cols = st.columns(len(submissions))
        for i, (node_id, payload) in enumerate(submissions.items()):
            used      = payload.get("epsilon", 0.0)
            remaining = max(0.0, EPSILON_BUDGET - used)
            pct       = remaining / EPSILON_BUDGET
            color     = "normal" if pct > 0.5 else ("off" if pct > 0.2 else "inverse")
            with budget_cols[i]:
                st.metric(
                    label=f"ε {node_id}",
                    value=f"{remaining:.2f} left",
                    delta=f"-{used:.2f} used",
                    delta_color="inverse",
                )
                st.progress(pct)

st.divider()

# ── Row 2.5: Data Variability per Node ───────────────────────────────────────
st.subheader("📊 Data Variability per Node")
st.caption("Noisy standard deviation per node — higher = more spread-out data")

if server_unreachable(results):
    st.error(results["error"])
else:
    subs = results.get("submissions", {})
    if not subs:
        st.info("No submissions yet.")
    else:
        std_cols = st.columns(len(subs))
        for i, (node_id, payload) in enumerate(subs.items()):
            std_val = payload.get("noisy_std")
            with std_cols[i]:
                if std_val is None:
                    st.metric(label=f"σ {node_id}", value="n/a")
                else:
                    st.metric(label=f"σ {node_id}", value=f"{std_val:.2f}")

st.divider()

# ── Row 3: Trend Chart ────────────────────────────────────────────────────────
st.subheader("📈 Aggregation History — Trend Chart")

history = fetch("/history")
if server_unreachable(history):
    st.error(history["error"])
elif isinstance(history, list) and history:
    import pandas as pd
    df = pd.DataFrame(history)
    st.line_chart(df.set_index("round")["aggregated_value"])
    st.dataframe(df, use_container_width=True)
else:
    st.info("No rounds completed yet — press Trigger below.")

st.divider()

# ── Row 4: CSV Download ───────────────────────────────────────────────────────
st.subheader("📥 Global Trend Report")

report = fetch("/reports")
if server_unreachable(report):
    st.warning("Reports not available yet.")
else:
    report_data = report.get("data", [])
    if report_data:
        import pandas as pd, io
        df_report = pd.DataFrame(report_data)

        # JSON download
        json_bytes = df_report.to_json(orient="records", indent=2).encode()
        st.download_button(
            label="⬇️ Download JSON Report",
            data=json_bytes,
            file_name="global_trend_report.json",
            mime="application/json",
        )

        # CSV download
        csv_buffer = io.StringIO()
        df_report.to_csv(csv_buffer, index=False)
        st.download_button(
            label="⬇️ Download CSV Report",
            data=csv_buffer.getvalue(),
            file_name="global_trend_report.csv",
            mime="text/csv",
        )
    else:
        st.info("No report data yet — trigger an aggregation round first.")

st.divider()

# ── Row 5: Raw Submissions ────────────────────────────────────────────────────
st.subheader("📦 Raw Node Submissions")
if server_unreachable(results):
    st.error(results["error"])
else:
    st.json(results)

# ── Trigger aggregation ───────────────────────────────────────────────────────
st.divider()
if st.button("⚡ Trigger FedAvg Aggregation Now"):
    try:
        r = requests.post(f"{SERVER_URL}/aggregate", timeout=5)
        st.success(f"Round complete: {r.json()}")
    except Exception as e:
        st.error(str(e))

# ── Auto-refresh (polls every 5 s by default) ─────────────────────────────────
time.sleep(refresh)
st.rerun()
