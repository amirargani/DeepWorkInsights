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
