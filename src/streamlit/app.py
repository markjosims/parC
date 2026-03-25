import streamlit as st
import pandas as pd

csv = st.file_uploader(
    label="Upload spreadsheet with sentences",
    type=["csv", "xlsx"],
)

if csv is not None:
    df = pd.read_csv(csv)
    st.write(df)
