"""Módulo de autenticación compartida para los dashboards de Finart."""
import hmac
import os
import streamlit as st


def _parse_users():
    """Permite configurar múltiples usuarios: USER1:PASS1,USER2:PASS2."""
    raw = os.getenv("DASHBOARD_USERS", "").strip()
    users = {}
    if raw:
        for pair in raw.split(","):
            if ":" in pair:
                u, p = pair.split(":", 1)
                users[u.strip()] = p.strip()
    return users


def verificar_autenticacion():
    """Autenticación corporativa. Soporta contraseña global o usuarios/contraseñas."""
    global_pass = os.getenv("DASHBOARD_PASSWORD")
    multi_users = _parse_users()

    # Si no hay ninguna contraseña configurada, permitir acceso libre (desarrollo local)
    if not global_pass and not multi_users:
        return True

    # Si ya se autenticó en la sesión activa
    if st.session_state.get("authenticated", False):
        return True

    # Renderizar pantalla de login corporativa
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style='text-align: center; padding: 2rem 0 1rem;'>
                <div style='font-size: 1.8rem; font-weight: 700; color: #0F172A; letter-spacing: -0.02em;'>
                    FINART S.A.S.
                </div>
                <div style='font-size: 0.95rem; color: #64748B; margin-top: 4px;'>
                    Portal Gerencial · Acceso Restringido
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("form_login"):
            usuario = None
            if multi_users:
                usuario = st.text_input("Usuario", key="login_user")
            clave = st.text_input("Contraseña de acceso", type="password", key="login_pass")
            submit = st.form_submit_button("Ingresar al Dashboard", use_container_width=True)

            if submit:
                valido = False
                if multi_users and usuario in multi_users:
                    if hmac.compare_digest(clave, multi_users[usuario]):
                        valido = True
                        st.session_state["user_role"] = usuario
                elif global_pass and hmac.compare_digest(clave, global_pass):
                    valido = True
                    st.session_state["user_role"] = "gerente"

                if valido:
                    st.session_state["authenticated"] = True
                    st.session_state["ok"] = True  # Compatibilidad con código anterior
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas. Verifique e intente nuevamente.")

        st.caption("Finart S.A.S. · Sistema de Inteligencia Comercial y Control de Inventarios.")
    st.stop()
    return False
