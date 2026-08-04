import pandas as pd
import streamlit as st
import plotly.express as px
import os
import io
import zipfile
from datetime import datetime

# ----------------------------
# Funções de dados (em memória, usando o Excel como base)
# Depois vamos trocar o "miolo" dessas funções por um banco SQL,
# mas a forma de chamar (buscar_saldo, adicionar_credito, registrar_venda)
# continua a mesma.
# ----------------------------

def carregar_alunos():
    alunos = "Alunos_2026_Matricula_Nome_Serie.xlsx"
    df = pd.read_excel(alunos)
    df["Matrícula"] = df["Matrícula"].astype(str)
    df["Saldo"] = 0.0
    return df

def carregar_estoque():
    caminho = "Estoque Cantina.xlsx"
    df = pd.read_excel(caminho)
    df["Quantidade em Estoque"] = df["Quantidade em Estoque"].fillna(0)
    return df

def buscar_preco(produto):
    df = st.session_state.df_estoque
    return df.loc[df["Produto"] == produto, "Preço de Venda"].iloc[0]

def buscar_quantidade_estoque(produto):
    df = st.session_state.df_estoque
    return df.loc[df["Produto"] == produto, "Quantidade em Estoque"].iloc[0]

def definir_quantidade_estoque(produto, quantidade_nova):
    df = st.session_state.df_estoque
    df.loc[df["Produto"] == produto, "Quantidade em Estoque"] = quantidade_nova

def baixar_estoque(produto, quantidade_vendida):
    df = st.session_state.df_estoque
    df.loc[df["Produto"] == produto, "Quantidade em Estoque"] -= quantidade_vendida

def inicializar_dados():
    if "df_alunos" not in st.session_state:
        st.session_state.df_alunos = carregar_alunos()

    if "df_estoque" not in st.session_state:
        st.session_state.df_estoque = carregar_estoque()

    if "df_vendas" not in st.session_state:
        st.session_state.df_vendas = pd.DataFrame(
            columns=["matricula", "nome_aluno", "item", "quantidade", "valor", "forma_pagamento", "data"]
        )

    if "df_solicitacoes" not in st.session_state:
        st.session_state.df_solicitacoes = pd.DataFrame(
            columns=["id", "matricula", "nome_aluno", "valor", "forma_pagamento",
                     "comprovante_nome", "comprovante_bytes", "status", "data"]
        )

def buscar_saldo(matricula):
    df = st.session_state.df_alunos
    linha = df[df["Matrícula"] == matricula]
    return linha["Saldo"].iloc[0]

def adicionar_credito(matricula, valor):
    df = st.session_state.df_alunos
    df.loc[df["Matrícula"] == matricula, "Saldo"] += valor

CAMINHO_VENDAS_EXCEL = "vendas_do_dia.xlsx"

def salvar_venda_no_excel(venda_dict):
    if os.path.exists(CAMINHO_VENDAS_EXCEL):
        df_existente = pd.read_excel(CAMINHO_VENDAS_EXCEL)
    else:
        df_existente = pd.DataFrame(columns=list(venda_dict.keys()))

    df_atualizado = pd.concat([df_existente, pd.DataFrame([venda_dict])], ignore_index=True)
    df_atualizado.to_excel(CAMINHO_VENDAS_EXCEL, index=False)

def registrar_venda(matricula, nome_aluno, item, quantidade, valor, forma_pagamento):
    if forma_pagamento == "Saldo do aluno":
        df_alunos = st.session_state.df_alunos
        df_alunos.loc[df_alunos["Matrícula"] == matricula, "Saldo"] -= valor

    baixar_estoque(item, quantidade)

    venda_dict = {
        "matricula": matricula,
        "nome_aluno": nome_aluno,
        "item": item,
        "quantidade": quantidade,
        "valor": valor,
        "forma_pagamento": forma_pagamento,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    st.session_state.df_vendas = pd.concat(
        [st.session_state.df_vendas, pd.DataFrame([venda_dict])], ignore_index=True
    )

    salvar_venda_no_excel(venda_dict)

PASTA_COMPROVANTES = "comprovantes_pix"

def solicitar_credito(matricula, nome_aluno, valor, forma_pagamento, arquivo=None, recebido_por=None):
    novo_id = len(st.session_state.df_solicitacoes) + 1

    if forma_pagamento == "Pix":
        comprovante_nome = arquivo.name
        comprovante_bytes = arquivo.getvalue()
        status = "Pendente"

        os.makedirs(PASTA_COMPROVANTES, exist_ok=True)
        extensao = comprovante_nome.split(".")[-1]
        nome_arquivo_disco = f"{novo_id}_{matricula}_{nome_aluno}.{extensao}"
        with open(os.path.join(PASTA_COMPROVANTES, nome_arquivo_disco), "wb") as arquivo_disco:
            arquivo_disco.write(comprovante_bytes)
    else:
        comprovante_nome = f"Dinheiro recebido por {recebido_por}"
        comprovante_bytes = None
        status = "Confirmado"

    nova_solicitacao = pd.DataFrame([{
        "id": novo_id,
        "matricula": matricula,
        "nome_aluno": nome_aluno,
        "valor": valor,
        "forma_pagamento": forma_pagamento,
        "comprovante_nome": comprovante_nome,
        "comprovante_bytes": comprovante_bytes,
        "status": status,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M")
    }])

    st.session_state.df_solicitacoes = pd.concat([st.session_state.df_solicitacoes, nova_solicitacao], ignore_index=True)

    if forma_pagamento == "Dinheiro":
        adicionar_credito(matricula, valor)

def confirmar_credito(id_solicitacao):
    df = st.session_state.df_solicitacoes
    solicitacao = df[df["id"] == id_solicitacao].iloc[0]

    adicionar_credito(solicitacao["matricula"], solicitacao["valor"])
    df.loc[df["id"] == id_solicitacao, "status"] = "Confirmado"

def recusar_credito(id_solicitacao):
    df = st.session_state.df_solicitacoes
    df.loc[df["id"] == id_solicitacao, "status"] = "Recusado"

FUNCIONARIOS_CANTINA = ["Luiz Felipe", "Vitória Wislet", "Gabriel Vitor"]

st.set_page_config(layout="wide", page_icon="", page_title="Cantina")
st.title("Controle da Cantina")
st.caption(f"Data e Hora:  {datetime.now().strftime('%d/%m/%Y %H:%M')}")

inicializar_dados()

if 'logado' not in st.session_state:
    st.session_state.logado = False

def verificar_login(usuario, senha):

    USUARIO_CORRETO = "admin_CMA"
    SENHA_CORRETO = "CMA2026"

    return usuario == USUARIO_CORRETO and senha == SENHA_CORRETO

if not st.session_state.logado:
    st.title("Login")

    usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
    senha = st.text_input("Senha", type="password",placeholder="Digite sua senha")

    if st.button("Entrar", use_container_width=True):
        if verificar_login(usuario=usuario,senha=senha):
            st.session_state.logado = True
            st.success("Login realizado com sucesso!")
            st.rerun()
        else:
            st.error(" Usuário ou senha incorretos!")

    st.stop()

col_titulo, col_logout = st.columns([4,1])
with col_titulo:
    st.title(" Controle da Cantina")
with col_logout:
    if st.button(" Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

aba_vendas, aba_estoque, aba_dashboard, aba_comprovantes = st.tabs(
    ["Registro de Vendas", "Estoque", "Dashboard", "Comprovantes"]
)

with aba_vendas:

    df_alunos = st.session_state.df_alunos

    nome_digitado = st.text_input("Digite o nome do Aluno", placeholder="Nome do Aluno")

    if nome_digitado:
        alunos_filtrados = df_alunos[df_alunos["Nome do aluno"].str.contains(nome_digitado, case=False)]
    else:
        alunos_filtrados = pd.DataFrame()

    if nome_digitado and alunos_filtrados.empty:
        st.warning("Nenhum aluno encontrado!")

    if not alunos_filtrados.empty:

        st.write("**Resultado da busca:**")
        st.dataframe(alunos_filtrados, use_container_width=True)

        opcoes_aluno = alunos_filtrados["Nome do aluno"] + " - Matrícula " + alunos_filtrados["Matrícula"].astype(str)
        aluno_escolhido = st.selectbox("Selecione o aluno", opcoes_aluno)

        nome_selecionado = aluno_escolhido.split(" - Matrícula ")[0]
        matricula_selecionada = aluno_escolhido.split(" - Matrícula ")[1]

        saldo_atual = buscar_saldo(matricula_selecionada)

        st.markdown("---")
        st.metric(f"Saldo de {nome_selecionado}", f"R$ {saldo_atual:.2f}")

        col_credito, col_venda = st.columns(2)

        with col_credito:
            st.write("**💰 Adicionar crédito**")

            forma_pagamento = st.radio(
                "Forma de pagamento", ["Pix", "Dinheiro"], horizontal=True, key="forma_pagamento_credito"
            )
            valor_credito = st.number_input("Valor (R$)", min_value=0.0, step=1.0, key="valor_credito")

            if forma_pagamento == "Pix":
                comprovante = st.file_uploader(
                    "Anexe o comprovante do Pix", type=["png", "jpg", "jpeg", "pdf"], key="comprovante_pix"
                )
            else:
                recebido_por = st.selectbox("Recebido por", FUNCIONARIOS_CANTINA, key="recebido_por")

            if st.button("Registrar crédito", use_container_width=True):

                if valor_credito <= 0:
                    st.warning("Informe um valor maior que zero.")

                elif forma_pagamento == "Pix" and comprovante is None:
                    st.warning("Anexe o comprovante antes de enviar.")

                elif forma_pagamento == "Pix":
                    solicitar_credito(matricula_selecionada, nome_selecionado, valor_credito, "Pix", arquivo=comprovante)
                    st.success("Comprovante enviado! O crédito será liberado após a conferência.")
                    st.rerun()

                else:
                    solicitar_credito(matricula_selecionada, nome_selecionado, valor_credito, "Dinheiro", recebido_por=recebido_por)
                    st.success("Crédito em dinheiro registrado e liberado imediatamente!")
                    st.rerun()

        with col_venda:
            st.write("**🛒 Registrar venda**")

            df_estoque = st.session_state.df_estoque

            produto_vendido = st.selectbox("Produto", df_estoque["Produto"], key="produto_vendido")
            preco_unitario = buscar_preco(produto_vendido)
            estoque_disponivel = buscar_quantidade_estoque(produto_vendido)

            quantidade_vendida = st.number_input(
                "Quantidade", min_value=1, value=1, step=1, key="quantidade_vendida"
            )

            valor_venda = preco_unitario * quantidade_vendida
            st.write(f"Preço unitário: R$ {preco_unitario:.2f}")
            st.write(f"**Valor total: R$ {valor_venda:.2f}**")
            st.caption(f"Estoque disponível: {int(estoque_disponivel)} unidades")

            forma_pagamento_venda = st.selectbox(
                "Forma de pagamento", ["Saldo do aluno", "Dinheiro", "Pix"], key="forma_pagamento_venda"
            )

            if st.button("Confirmar venda", use_container_width=True):

                if quantidade_vendida > estoque_disponivel:
                    st.error("Quantidade maior que o estoque disponível!")

                else:
                    if forma_pagamento_venda == "Saldo do aluno" and valor_venda > saldo_atual:
                        st.warning("Atenção: essa venda vai deixar o saldo negativo.")

                    registrar_venda(
                        matricula_selecionada, nome_selecionado, produto_vendido,
                        quantidade_vendida, valor_venda, forma_pagamento_venda
                    )
                    st.success("Venda registrada com sucesso!")
                    st.rerun()

        st.markdown("---")
        st.subheader(f"📜 Histórico de compras — {nome_selecionado}")

        df_vendas = st.session_state.df_vendas
        historico_vendas = df_vendas[df_vendas["matricula"] == matricula_selecionada]

        if historico_vendas.empty:
            st.info("Nenhuma compra registrada para este aluno ainda.")
        else:
            historico_vendas_exibicao = historico_vendas[["item", "quantidade", "valor", "forma_pagamento", "data"]].sort_values("data", ascending=False)
            st.dataframe(historico_vendas_exibicao, use_container_width=True)

with aba_estoque:

    st.subheader("📦 Estoque atual")

    df_estoque = st.session_state.df_estoque
    st.dataframe(df_estoque, use_container_width=True)

    st.markdown("---")
    st.write("**Atualizar quantidade de um produto**")
    st.caption("Use aqui para o cadastro inicial das quantidades ou para repor estoque.")

    col_produto, col_quantidade, col_botao = st.columns([2, 1, 1])

    with col_produto:
        produto_ajuste = st.selectbox("Produto", df_estoque["Produto"], key="produto_ajuste")

    with col_quantidade:
        quantidade_ajuste = st.number_input(
            "Nova quantidade", min_value=0, step=1,
            value=int(buscar_quantidade_estoque(produto_ajuste)), key="quantidade_ajuste"
        )

    with col_botao:
        st.write("")
        st.write("")
        if st.button("Atualizar", use_container_width=True):
            definir_quantidade_estoque(produto_ajuste, quantidade_ajuste)
            st.success(f"Estoque de {produto_ajuste} atualizado para {quantidade_ajuste} unidades!")
            st.rerun()

with aba_dashboard:

    st.subheader("📊 Dashboard de resultados")

    df_vendas = st.session_state.df_vendas

    if df_vendas.empty:
        st.info("Nenhuma venda registrada ainda.")
    else:
        total_vendas = len(df_vendas)
        faturamento_total = df_vendas["valor"].sum()
        ticket_medio = faturamento_total / total_vendas
        saldo_total_carteira = st.session_state.df_alunos["Saldo"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de vendas", total_vendas)
        col2.metric("Faturamento total", f"R$ {faturamento_total:.2f}")
        col3.metric("Ticket médio", f"R$ {ticket_medio:.2f}")
        col4.metric("Saldo total em carteira", f"R$ {saldo_total_carteira:.2f}")

        st.markdown("---")

        col_esquerda, col_direita = st.columns(2)

        with col_esquerda:
            vendas_por_aluno = df_vendas.groupby("nome_aluno")["valor"].sum().reset_index()
            vendas_por_aluno = vendas_por_aluno.sort_values("valor", ascending=False).head(10)
            fig_alunos = px.bar(
                vendas_por_aluno, x="nome_aluno", y="valor",
                title="Top 10 alunos por valor gasto", text_auto=True
            )
            st.plotly_chart(fig_alunos, use_container_width=True)

        with col_direita:
            vendas_por_item = df_vendas.groupby("item")["valor"].sum().reset_index()
            fig_itens = px.pie(vendas_por_item, names="item", values="valor", title="Faturamento por item")
            st.plotly_chart(fig_itens, use_container_width=True)

        vendas_por_forma = df_vendas.groupby("forma_pagamento")["valor"].sum().reset_index()
        fig_forma_venda = px.bar(
            vendas_por_forma, x="forma_pagamento", y="valor",
            title="Vendas por forma de pagamento", text_auto=True
        )
        st.plotly_chart(fig_forma_venda, use_container_width=True)

        df_vendas["dia"] = df_vendas["data"].str.split(" ").str[0]
        vendas_por_dia = df_vendas.groupby("dia")["valor"].sum().reset_index()
        fig_dia = px.line(vendas_por_dia, x="dia", y="valor", title="Faturamento por dia", markers=True)
        st.plotly_chart(fig_dia, use_container_width=True)

    st.markdown("---")
    st.subheader("💰 Créditos (Pix) confirmados")

    confirmados = st.session_state.df_solicitacoes
    confirmados = confirmados[confirmados["status"] == "Confirmado"]

    if confirmados.empty:
        st.info("Nenhum crédito confirmado ainda.")
    else:
        total_creditado = confirmados["valor"].sum()
        st.metric("Total creditado (confirmado)", f"R$ {total_creditado:.2f}")

        creditos_por_dia = confirmados.copy()
        creditos_por_dia["dia"] = creditos_por_dia["data"].str.split(" ").str[0]
        creditos_por_dia = creditos_por_dia.groupby("dia")["valor"].sum().reset_index()

        col_esquerda_credito, col_direita_credito = st.columns(2)

        with col_esquerda_credito:
            fig_creditos = px.bar(creditos_por_dia, x="dia", y="valor", title="Créditos confirmados por dia", text_auto=True)
            st.plotly_chart(fig_creditos, use_container_width=True)

        with col_direita_credito:
            creditos_por_forma = confirmados.groupby("forma_pagamento")["valor"].sum().reset_index()
            fig_forma = px.pie(creditos_por_forma, names="forma_pagamento", values="valor", title="Créditos por forma de pagamento")
            st.plotly_chart(fig_forma, use_container_width=True)

    st.markdown("---")
    st.subheader("📥 Fechamento do dia")

    col_download_vendas, col_download_comprovantes = st.columns(2)

    with col_download_vendas:
        if os.path.exists(CAMINHO_VENDAS_EXCEL):
            with open(CAMINHO_VENDAS_EXCEL, "rb") as arquivo_vendas:
                st.download_button(
                    "Baixar vendas do dia (Excel)",
                    data=arquivo_vendas,
                    file_name="vendas_do_dia.xlsx",
                    use_container_width=True
                )
        else:
            st.info("Nenhuma venda registrada ainda hoje.")

    with col_download_comprovantes:
        if os.path.exists(PASTA_COMPROVANTES) and os.listdir(PASTA_COMPROVANTES):
            buffer_zip = io.BytesIO()
            with zipfile.ZipFile(buffer_zip, "w") as arquivo_zip:
                for nome_arquivo in os.listdir(PASTA_COMPROVANTES):
                    caminho_completo = os.path.join(PASTA_COMPROVANTES, nome_arquivo)
                    arquivo_zip.write(caminho_completo, arcname=nome_arquivo)

            st.download_button(
                "Baixar comprovantes Pix (.zip)",
                data=buffer_zip.getvalue(),
                file_name="comprovantes_pix.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            st.info("Nenhum comprovante Pix enviado ainda hoje.")

with aba_comprovantes:

    st.subheader("🧾 Conferência de comprovantes")

    df_solic = st.session_state.df_solicitacoes
    pendentes = df_solic[df_solic["status"] == "Pendente"]

    if pendentes.empty:
        st.info("Nenhum comprovante pendente de conferência.")
    else:
        for _, solicitacao in pendentes.iterrows():

            titulo = f"{solicitacao['nome_aluno']} — R$ {solicitacao['valor']:.2f} — {solicitacao['data']}"

            with st.expander(titulo):
                nome_arquivo = solicitacao["comprovante_nome"]
                bytes_arquivo = solicitacao["comprovante_bytes"]

                if nome_arquivo.lower().endswith((".png", ".jpg", ".jpeg")):
                    st.image(bytes_arquivo, caption=nome_arquivo, width=300)
                else:
                    st.write(f"Arquivo anexado: {nome_arquivo}")
                    st.download_button(
                        "Baixar comprovante", data=bytes_arquivo,
                        file_name=nome_arquivo, key=f"download_{solicitacao['id']}"
                    )

                col_confirmar, col_recusar = st.columns(2)

                with col_confirmar:
                    if st.button("✅ Confirmar", key=f"confirmar_{solicitacao['id']}", use_container_width=True):
                        confirmar_credito(solicitacao["id"])
                        st.success("Crédito liberado!")
                        st.rerun()

                with col_recusar:
                    if st.button("❌ Recusar", key=f"recusar_{solicitacao['id']}", use_container_width=True):
                        recusar_credito(solicitacao["id"])
                        st.warning("Comprovante recusado.")
                        st.rerun()

    st.markdown("---")
    st.subheader("📜 Histórico de conferências")

    historico = df_solic[df_solic["status"] != "Pendente"]

    if historico.empty:
        st.info("Nenhuma conferência realizada ainda.")
    else:
        historico_exibicao = historico[["nome_aluno", "valor", "forma_pagamento", "data", "status"]].sort_values("data", ascending=False)
        st.dataframe(historico_exibicao, use_container_width=True)