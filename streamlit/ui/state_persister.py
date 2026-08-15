import streamlit as st
import streamlit.components.v1 as components


def render_lang_persister():
    """Renders inline JS via st.components.v1 to persist and hydrate selected language in browser localStorage."""
    _lang = st.session_state.get("language", "EN")
    _hydrated = st.session_state.get("language_hydrated", False)

    components.html(
        f"""
<script>
(function() {{
    var p = window.parent;
    var pdoc = p.document;
    var stored = localStorage.getItem("streamlit_language");

    if (!{str(_hydrated).lower()} && stored && (stored === "EN" || stored === "DE") && stored !== "{_lang}") {{
        var labels = pdoc.querySelectorAll('label');
        for (var i = 0; i < labels.length; i++) {{
            if (labels[i].innerText && labels[i].innerText.trim() === stored) {{
                labels[i].click();
                break;
            }}
        }}
    }} else {{
        localStorage.setItem("streamlit_language", "{_lang}");
    }}
}})();
</script>
        """,
        height=0,
    )
    st.session_state.language_hydrated = True
