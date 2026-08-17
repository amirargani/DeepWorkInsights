"""Scroll position persistence component module.

Injects inline HTML/JS onerror handlers into the Streamlit DOM to preserve
and restore the window/container scroll position across app reruns.
"""

import time
import streamlit as st


def render_scroll_persister(current_tab: str):
    """Inline HTML onerror script to maintain scroll state across reruns of the same tab."""
    render_key = int(time.time() * 1000)
    scroll_js = (
        f'<img src="x?r={render_key}" onerror="const currentTab=\'{current_tab}\'; '
        f"if (window.scrollRestorerInterval) clearInterval(window.scrollRestorerInterval); "
        f"const savedScroll=sessionStorage.getItem('scrollPosition_'+currentTab); "
        f"const prevTab=sessionStorage.getItem('prevTab'); "
        f"sessionStorage.setItem('prevTab',currentTab); "
        f"if (savedScroll!==null && parseInt(savedScroll)>0) {{ "
        f"window.isRestoringScroll=true; let ticks=0; "
        f"window.scrollRestorerInterval=setInterval(()=>{{ ticks++; const val=parseInt(savedScroll); "
        f"const main=document.querySelector('.main'); const stApp=document.querySelector('.stApp'); "
        f"let success=false; [main,stApp].forEach(c=>{{ if (c && c.scrollTop!==undefined) {{ "
        f"c.scrollTop=val; if (Math.abs(c.scrollTop-val)<5) success=true; }} }}); "
        f"if (success || ticks>40) {{ clearInterval(window.scrollRestorerInterval); "
        f"setTimeout(()=>{{ window.isRestoringScroll=false; }},50); }} }},25); "
        f"}} else if (prevTab!==null && prevTab!==currentTab) {{ window.isRestoringScroll=false; const resetScroll=()=>{{ "
        f"const containers=[document.querySelector('.main'),document.querySelector('.stApp')]; "
        f"containers.forEach(c=>{{ if (c && c.scrollTop!==undefined) c.scrollTop=0; }}); "
        f"window.scrollTo({{top:0,behavior:'auto'}}); }}; resetScroll(); setTimeout(resetScroll,50); }} "
        f"sessionStorage.setItem('activeTab',currentTab); "
        f"if (window.onStreamlitScroll) window.removeEventListener('scroll',window.onStreamlitScroll,true); "
        f"window.onStreamlitScroll=()=>{{ if (window.isRestoringScroll) return; "
        f"const activeTab=sessionStorage.getItem('activeTab')||currentTab; "
        f"const main=document.querySelector('.main'); const stApp=document.querySelector('.stApp'); "
        f"let pos=0; if (main && main.scrollTop!==undefined && main.scrollTop>0) {{ pos=main.scrollTop; }} "
        f"else if (stApp && stApp.scrollTop!==undefined && stApp.scrollTop>0) {{ pos=stApp.scrollTop; }} "
        f"else if (window.scrollY>0) {{ pos=window.scrollY; }} "
        f"if (pos>0) {{ sessionStorage.setItem('scrollPosition_'+activeTab,pos); }} }}; "
        f"window.addEventListener('scroll',window.onStreamlitScroll,true);\" style=\"display:none;\"/>"
    )
    st.markdown(scroll_js, unsafe_allow_html=True)


def render_fragment_scroll_guard(fragment_key: str):
    """Inject a lightweight scroll guard for fragment reruns (run_every).

    When a @st.fragment(run_every=...) reruns, Streamlit patches only that
    section of the DOM. This can reset the browser scroll position to the top.

    This guard saves the current scroll position and restores it after Streamlit
    finishes patching the fragment DOM, using a MutationObserver.

    Call this once at the TOP of any fragment function that uses run_every.

    Args:
        fragment_key: A unique string key per fragment (e.g. "docker", "airflow", "logs").
                      Used to namespace the sessionStorage entry.
    """
    guard_key = int(time.time() * 1000)
    # Single-line format is required — st.markdown breaks on multiline onerror attributes
    js = (
        f'<img src="x?fgk={guard_key}" onerror="(function(){{'
        f"var SK='fragScroll_{fragment_key}';"
        f"var getS=function(){{var m=document.querySelector('.main');var a=document.querySelector('.stApp');"
        f"if(m&&m.scrollTop>0)return m.scrollTop;if(a&&a.scrollTop>0)return a.scrollTop;return window.scrollY||0;}};"
        f"var restore=function(p){{if(!p||p<5)return;var t=0;var iv=setInterval(function(){{"
        f"t++;var m=document.querySelector('.main');var a=document.querySelector('.stApp');"
        f"if(m&&m.scrollTop!==undefined)m.scrollTop=p;if(a&&a.scrollTop!==undefined)a.scrollTop=p;"
        f"if(t>30)clearInterval(iv);}},20);}};"
        f"var pos=getS();if(pos>5)sessionStorage.setItem(SK,pos);"
        f"var saved=parseInt(sessionStorage.getItem(SK)||'0');"
        f"if(saved>5){{"
        f"var tgt=document.querySelector('.stApp')||document.body;"
        f"if(window._fObs_{fragment_key})window._fObs_{fragment_key}.disconnect();"
        f"window._fObs_{fragment_key}=new MutationObserver(function(m,obs){{obs.disconnect();restore(saved);}});"
        f"window._fObs_{fragment_key}.observe(tgt,{{childList:true,subtree:true}});"
        f"}}"
        f'}})();" style="display:none;"/>'
    )
    st.markdown(js, unsafe_allow_html=True)
