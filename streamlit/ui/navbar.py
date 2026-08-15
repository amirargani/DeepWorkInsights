import streamlit as st
import streamlit.components.v1 as components


def _on_nav_tab_change():
    selected = st.session_state.nav_tab_radio
    new_tab = "dashboard" if selected == "Forecasting" else "monitoring"
    st.session_state.active_tab = new_tab
    st.query_params["tab"] = new_tab


def _on_nav_lang_change():
    st.session_state.language = st.session_state.nav_lang_radio


def render_navbar():
    """Renders the hidden radio widgets and floating sticky navigation bar."""
    # Hidden navigation tab selector to support floating navbar switching
    st.radio(
        "Navigation Tab",
        options=["Forecasting", "Monitoring"],
        index=0 if st.session_state.active_tab == "dashboard" else 1,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_tab_radio",
        on_change=_on_nav_tab_change,
    )

    # Hidden language selector to support floating navbar switching
    st.radio(
        "Language / Sprache",
        options=["EN", "DE"],
        index=0 if st.session_state.language == "EN" else 1,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_lang_radio",
        on_change=_on_nav_lang_change,
    )

    # Sticky mini-nav HTML/JS component
    _active = st.session_state.active_tab
    _lang = st.session_state.language
    components.html(
        f"""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,400,0,0" rel="stylesheet">
<style>
@keyframes topNavSpin {{
    0% {{ transform: rotate(0deg); }}
    100% {{ transform: rotate(360deg); }}
}}
@keyframes topNavLoadbar {{
    0% {{ left: -40%; width: 40%; }}
    50% {{ left: 30%; width: 50%; }}
    100% {{ left: 100%; width: 40%; }}
}}
.top-nav-spinning {{
    display: inline-block !important;
    animation: topNavSpin 0.8s linear infinite !important;
}}
</style>
<script>
(function() {{
    var p    = window.parent;
    var pdoc = p.document;

    var old = pdoc.getElementById('smn');
    if (old) old.remove();

    var oldBar = pdoc.getElementById('smn-loadbar');
    if (oldBar) oldBar.remove();

    var oldOverlay = pdoc.getElementById('smn-overlay');
    if (oldOverlay) oldOverlay.remove();

    var activeTab = '{_active}';
    var activeLang = '{_lang}';

    function showTopLoadbar() {{
        if (pdoc.getElementById('smn-loadbar')) return;
        var barContainer = pdoc.createElement('div');
        barContainer.id = 'smn-loadbar';
        barContainer.style.cssText = [
            'position:fixed','top:0','left:0','right:0','height:3px',
            'z-index:999999','overflow:hidden','background:rgba(76,139,245,0.15)'
        ].join(';');

        var bar = pdoc.createElement('div');
        bar.style.cssText = [
            'position:absolute','top:0','bottom:0',
            'background:linear-gradient(90deg, #4c8bf5, #00f2fe, #4c8bf5)',
            'box-shadow:0 0 10px #4c8bf5',
            'animation:topNavLoadbar 1.2s infinite ease-in-out'
        ].join(';');

        barContainer.appendChild(bar);
        pdoc.body.appendChild(barContainer);
    }}

    // Click a radio option label by its exact text
    function clickRadio(labelText, btnElement) {{
        showTopLoadbar();
        if (btnElement) {{
            var iconSpan = btnElement.querySelector('.nav-icon');
            if (iconSpan) {{
                iconSpan.textContent = 'progress_activity';
                iconSpan.classList.add('top-nav-spinning');
            }}
            btnElement.style.opacity = '0.7';
            btnElement.style.pointerEvents = 'none';
        }}

        // Instantly hide previous tab content using display: none
        try {{
            var mainBlock = pdoc.querySelector('.main .block-container');
            if (mainBlock && mainBlock.children) {{
                for (var i = 1; i < mainBlock.children.length; i++) {{
                    mainBlock.children[i].style.display = 'none';
                }}
            }}
        }} catch(e) {{}}

        var labels = pdoc.querySelectorAll('label');
        for (var i = 0; i < labels.length; i++) {{
            if (labels[i].innerText && labels[i].innerText.trim() === labelText) {{
                labels[i].click(); return;
            }}
        }}
    }}

    function makeBtn(label, icon, isActive, clickFn) {{
        var a = pdoc.createElement('a');
        a.style.cssText = [
            'display:inline-flex','align-items:center','gap:4px',
            'font-size:12px','font-weight:500','padding:5px 12px',
            'border-radius:7px','cursor:pointer','text-decoration:none',
            'font-family:Source Sans Pro,sans-serif','white-space:nowrap',
            'transition:opacity .15s,transform .15s',
            isActive
                ? 'background:#4c8bf5;color:#fff;border:1.5px solid #4c8bf5;'
                : 'background:rgba(255,255,255,.05);color:#c9d1d9;border:1.5px solid rgba(255,255,255,.15);'
        ].join(';');
        a.onmouseover = function() {{ if (a.style.pointerEvents !== 'none') {{ a.style.opacity='.82'; a.style.transform='translateY(-1px)'; }} }};
        a.onmouseout  = function() {{ if (a.style.pointerEvents !== 'none') {{ a.style.opacity='1';   a.style.transform='translateY(0)'; }} }};
        a.onclick = function(e) {{ e.preventDefault(); clickFn(a); }};
        if (icon) {{
            var ic = pdoc.createElement('span');
            ic.className = 'nav-icon';
            ic.style.cssText = 'font-family:Material Symbols Rounded;font-size:14px;line-height:1;';
            ic.textContent = icon;
            a.appendChild(ic);
            a.appendChild(pdoc.createTextNode('\\u00a0'));
        }}
        a.appendChild(pdoc.createTextNode(label));
        return a;
    }}

    function makeDivider() {{
        var d = pdoc.createElement('div');
        d.style.cssText = 'width:1px;height:20px;background:rgba(255,255,255,.15);margin:0 2px;';
        return d;
    }}

    var nav = pdoc.createElement('div');
    nav.id = 'smn';
    nav.style.cssText = [
        'position:fixed','top:52px','right:20px','z-index:9999',
        'display:flex','gap:6px','align-items:center',
        'background:rgba(14,17,23,.88)','backdrop-filter:blur(12px)',
        '-webkit-backdrop-filter:blur(12px)',
        'border:1px solid rgba(255,255,255,.09)','border-radius:10px',
        'padding:5px 9px','box-shadow:0 4px 24px rgba(0,0,0,.45)'
    ].join(';');

    nav.appendChild(makeBtn('Forecasting', 'bar_chart',   activeTab === 'dashboard',  function(el) {{ if (activeTab === 'dashboard') return; clickRadio('Forecasting', el); }}));
    nav.appendChild(makeBtn('Monitoring',  'monitoring',  activeTab === 'monitoring', function(el) {{ if (activeTab === 'monitoring') return; clickRadio('Monitoring', el);  }}));
    nav.appendChild(makeDivider());
    nav.appendChild(makeBtn('EN', null, activeLang === 'EN', function(el) {{ if (activeLang === 'EN') return; clickRadio('EN', el); }}));
    nav.appendChild(makeBtn('DE', null, activeLang === 'DE', function(el) {{ if (activeLang === 'DE') return; clickRadio('DE', el); }}));
    pdoc.body.appendChild(nav);
}})();
</script>
""",
        height=0,
    )
