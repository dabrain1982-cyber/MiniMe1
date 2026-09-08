"""Two aligned, locally rendered month charts with synchronized scrolling."""
from html import escape


def timeline_html(months, growth, amazon, money):
    panels = []
    for title, values, color in [('Dein Kontozuwachs pro Monat', growth, '#159c62'), ('Amazon-Ausgaben pro Monat', amazon, '#5271ee')]:
        low, high = min(0, min(values)), max(0, max(values))
        span = max(high - low, 1)
        baseline = 22 + high / span * 140
        cells = []
        for month, value in zip(months, values):
            endpoint = 22 + (high - value) / span * 140
            top, height = min(endpoint, baseline), abs(endpoint - baseline)
            label = escape(money(value, force_sign=title.startswith('Dein')))
            cells.append(f'<div class="month-cell"><div style="height:190px;position:relative" role="img" aria-label="{escape(month)}: {label}"><div style="position:absolute;left:0;right:0;top:{baseline}px;border-top:1px solid #cbd5e1"></div><div style="position:absolute;left:25%;width:50%;top:{top}px;height:{height}px;border-radius:4px;background:{color if value >= 0 else "#d65754"}"></div><div style="position:absolute;left:0;right:0;top:{max(0, top-22)}px;font-size:12px">{label}</div></div><span>{escape(month)}</span></div>')
        panels.append(f'<section class="timeline-panel"><h3>{title}</h3><div class="month-scroll" tabindex="0" aria-label="{title}, horizontal scrollbar"><div class="month-grid" style="grid-template-columns:repeat({len(months)},minmax(140px,1fr));min-width:{len(months)*140}px">{"".join(cells)}</div></div></section>')
    return '''<style>
    #month-timeline{width:100%;min-width:0} .timeline-panel{padding:18px;border:1px solid #dfe5ef;border-radius:20px;margin-bottom:16px}
    .timeline-panel h3{margin:0 0 12px;font-size:22px}.month-scroll{overflow-x:auto;cursor:grab;touch-action:pan-x pan-y;scrollbar-width:auto}
    .month-scroll:active{cursor:grabbing}.month-grid{display:grid;width:100%;user-select:none}.month-cell{text-align:center;font:13px 'Segoe UI',sans-serif;color:#172033}
    .month-cell svg{display:block;width:100%;height:190px}.month-cell span{display:block;padding-bottom:12px}
    #month-timeline button{border:1px solid #cbd5e1;background:white;border-radius:8px;padding:6px 12px;cursor:pointer}
    </style><div id="month-timeline"><p style="font-size:13px">Beide Zeitachsen laufen gemeinsam. Mit Maus, Touch oder Scrollleiste zurückblättern. <button type="button">Zum neuesten Monat →</button></p>''' + ''.join(panels) + '''<p style="font-size:12px">Kontozuwachs = Endstand minus Anfangsstand, einschließlich Erstattungen. Amazon enthält Prime. Die Betragsmaßstäbe sind je Diagramm unterschiedlich.</p></div>
    <script>(()=>{const root=document.getElementById('month-timeline');if(!root)return;
    const rows=[...root.querySelectorAll('.month-scroll')];
    rows.forEach(row=>{row.addEventListener('scroll',()=>rows.forEach(other=>{if(other!==row&&Math.abs(other.scrollLeft-row.scrollLeft)>1)other.scrollLeft=row.scrollLeft}));
    let down=false,start=0,left=0;
    row.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse'||e.button!==0)return;down=true;start=e.clientX;left=row.scrollLeft;row.setPointerCapture(e.pointerId)});
    row.addEventListener('pointermove',e=>{if(down){row.scrollLeft=left+start-e.clientX;e.preventDefault()}});
    row.addEventListener('pointerup',()=>down=false);row.addEventListener('pointercancel',()=>down=false);});
    const latest=()=>rows.forEach(row=>row.scrollLeft=row.scrollWidth);root.querySelector('button').onclick=latest;
    requestAnimationFrame(latest);
    })()</script>'''
