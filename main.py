import streamlit as st
import sqlite3

#frontend
st.set_page_config(page_title="Formulário de Inscrição", page_icon=":pencil:", layout="centered")

st.title("Formulário de Inscrição")
name = st.text_input("Nome")
email = st.text_input("Email")

button = st.button("Inscrever")

#backend
if button:
    
    conn = sqlite3.connect("base.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inscritos (nome, email) VALUES (?, ?)", (name, email))
    conn.commit()
    conn.close()

    st.success("Inscrição realizada com sucesso!")
    st.balloons()