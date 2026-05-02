import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px

st.set_page_config(page_title="PdM Data Quality Summary", layout="wide")
st.title("Predictive Maintenance — Data Quality Summary")

df_telemetry = pd.read_csv('data/PdM_telemetry.csv')
df_errors    = pd.read_csv('data/PdM_errors.csv')
df_failures  = pd.read_csv('data/PdM_failures.csv')
df_maint     = pd.read_csv('data/PdM_maint.csv')
df_machines  = pd.read_csv('data/PdM_machines.csv')

for df in [df_telemetry, df_errors, df_failures, df_maint]:
    df['datetime'] = pd.to_datetime(df['datetime']).dt.floor('h')

conn = duckdb.connect()
conn.register('df_telemetry', df_telemetry)
conn.register('df_errors',    df_errors)
conn.register('df_failures',  df_failures)
conn.register('df_maint',     df_maint)
conn.register('df_machines',  df_machines)

st.subheader("Referential Integrity")
dq1 = conn.execute("""
    select 'errors'   as source_table, count(*) as orphaned_rows from df_errors   where machineID not in (select machineID from df_machines)
    union all
    select 'failures' as source_table, count(*) as orphaned_rows from df_failures where machineID not in (select machineID from df_machines)
    union all
    select 'maint'    as source_table, count(*) as orphaned_rows from df_maint    where machineID not in (select machineID from df_machines)
""").fetch_df()
st.dataframe(dq1, use_container_width=True)
if dq1['orphaned_rows'].sum() == 0:
    st.success("No referential integrity violations found across all tables.")
else:
    st.error("Referential integrity violations detected.")

st.subheader("Telemetry Completeness")
dq2 = conn.execute("""
    with time_spine as (
        select generate_series as hour
        from generate_series(
            (select min(datetime) from df_telemetry),
            (select max(datetime) from df_telemetry),
            interval '1 hour'
        )
    ),
    expected as (
        select m.machineID, ts.hour
        from df_machines m
        cross join time_spine ts
    ),
    actual as (
        select machineID, datetime as hour from df_telemetry
    )
    select
        count(*) as total_expected,
        sum(case when a.machineID is null then 1 else 0 end) as missing_rows,
        round(sum(case when a.machineID is null then 1 else 0 end) * 100.0 / count(*), 4) as pct_missing
    from expected e
    left join actual a on e.machineID = a.machineID and e.hour = a.hour
""").fetch_df()
col1, col2, col3 = st.columns(3)
col1.metric("Total expected rows", f"{dq2['total_expected'][0]:,}")
col2.metric("Missing rows",        f"{dq2['missing_rows'][0]:,}")
col3.metric("% missing",           f"{dq2['pct_missing'][0]}%")

st.subheader("Failure Distribution by Model")
failure_dist = conn.execute("""
    select m.model, count(*) as failures
    from df_failures f
    join df_machines m on f.machineID = m.machineID
    group by m.model
    order by failures desc
""").fetch_df()
fig = px.bar(failure_dist, x='model', y='failures', title='Failures by machine model')
st.plotly_chart(fig, use_container_width=True)
