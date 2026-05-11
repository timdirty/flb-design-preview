import{j as r}from"./motion-DZSGaD9S.js";import{r as s}from"./ui-YdmB7tzp.js";function m(a){return a.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/`(.+?)`/g,'<code class="px-1 py-0.5 rounded text-xs" style="background:var(--widget-code-bg, rgba(0,0,0,0.06))">$1</code>').replace(/\[\[nav:(student|teacher|course):([^\]:]+):([^\]]+)\]\]/g,'<button class="widget-nav-btn" data-nav-target="$1" data-nav-id="$2">$3 →</button>').replace(/\n/g,"<br />")}const x="widget-nav-btn-style";function v(){if(document.getElementById(x))return;const a=document.createElement("style");a.id=x,a.textContent=`
    .widget-nav-btn {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 10px 3px 8px;
      margin: 3px 2px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      line-height: 1.5;
      color: var(--widget-primary, #8b5cf6);
      background: var(--widget-nav-bg, rgba(139, 92, 246, 0.08));
      border: 1px solid var(--widget-nav-border, rgba(139, 92, 246, 0.2));
      cursor: pointer;
      transition: all 0.2s ease;
      font-family: inherit;
      vertical-align: middle;
      text-decoration: none;
      white-space: nowrap;
    }
    .widget-nav-btn::before {
      content: "↗";
      font-size: 11px;
      opacity: 0.7;
    }
    .widget-nav-btn:hover {
      background: var(--widget-nav-hover, rgba(139, 92, 246, 0.16));
      border-color: var(--widget-nav-hover-border, rgba(139, 92, 246, 0.4));
      box-shadow: 0 1px 4px rgba(139, 92, 246, 0.15);
      transform: translateY(-0.5px);
    }
    .widget-nav-btn:active {
      transform: scale(0.96) translateY(0);
      box-shadow: none;
    }
    .widget-nav-btn.clicked {
      opacity: 0.5;
      pointer-events: none;
    }
  `,document.head.appendChild(a)}function w({messages:a,botName:i,isTyping:g,onNavigate:n}){const l=s.useRef(null),d=s.useRef(null);s.useEffect(()=>{v()},[]),s.useEffect(()=>{const t=d.current;if(!t)return;t.scrollHeight-t.scrollTop-t.clientHeight<120&&l.current?.scrollIntoView({behavior:"smooth"})},[a.length,g]),s.useEffect(()=>{l.current?.scrollIntoView({behavior:"instant"})},[]);const c=s.useCallback(t=>{const e=t.target.closest(".widget-nav-btn");if(!e||e.classList.contains("clicked"))return;t.preventDefault();const f=e.dataset.navTarget,u=e.dataset.navId??"",p=e.textContent?.replace(/\s*↗?\s*→?$/,"").trim()??"";f&&u&&n&&(e.classList.add("clicked"),e.textContent="已開啟 ✓",n({target:f,id:u,label:p}),setTimeout(()=>{e.classList.remove("clicked"),e.textContent=`↗ ${p} →`},1500))},[n]);return r.jsxs("div",{ref:d,role:"log","aria-live":"polite","aria-label":"聊天訊息",className:"flex-1 overflow-y-auto px-3 py-4 space-y-3",style:{background:"var(--widget-bg, #f9fafb)"},onClick:c,onKeyDown:t=>{if(t.key==="Enter"||t.key===" "){const e=t.target.closest(".widget-nav-btn");e&&e.click()}},children:[a.map(t=>{const e=t.role==="user";return r.jsxs("div",{className:`flex ${e?"justify-end":"justify-start"} items-end gap-2`,children:[!e&&r.jsx("div",{className:"w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0",style:{background:"var(--widget-primary, var(--ds-color-primary))",color:"#ffffff"},"aria-hidden":"true",children:i.charAt(0).toUpperCase()}),r.jsx("div",{className:`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed break-words ${e?"rounded-br-md":"rounded-bl-md"}`,style:e?{background:"var(--widget-primary, var(--ds-color-primary))",color:"#ffffff"}:{background:"var(--widget-bubble-bg, #ffffff)",color:"var(--widget-text, #1f2937)",border:"1px solid var(--widget-bubble-border, rgba(0,0,0,0.08))"},dangerouslySetInnerHTML:{__html:m(t.content)}})]},t.id)}),g&&r.jsxs("div",{className:"flex justify-start items-end gap-2",children:[r.jsx("div",{className:"w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0",style:{background:"var(--widget-primary, var(--ds-color-primary))",color:"#ffffff"},"aria-hidden":"true",children:i.charAt(0).toUpperCase()}),r.jsx("div",{className:"rounded-2xl rounded-bl-md px-4 py-3",style:{background:"var(--widget-bubble-bg, #ffffff)",border:"1px solid var(--widget-bubble-border, rgba(0,0,0,0.08))"},children:r.jsxs("div",{className:"flex items-center gap-1","aria-label":"正在輸入中",children:[r.jsx("span",{className:"w-2 h-2 rounded-full animate-bounce",style:{background:"var(--widget-typing-dot, #9ca3af)",animationDelay:"0ms"}}),r.jsx("span",{className:"w-2 h-2 rounded-full animate-bounce",style:{background:"var(--widget-typing-dot, #9ca3af)",animationDelay:"150ms"}}),r.jsx("span",{className:"w-2 h-2 rounded-full animate-bounce",style:{background:"var(--widget-typing-dot, #9ca3af)",animationDelay:"300ms"}})]})})]}),r.jsx("div",{ref:l})]})}function k({onSend:a,disabled:i=!1,placeholder:g="輸入訊息..."}){const[n,l]=s.useState(""),d=s.useRef(null),c=500,t=n.length>c,e=n.trim().length>0&&!i&&!t,f=s.useCallback(()=>{const o=n.trim();!o||i||(a(o),l(""),d.current&&(d.current.style.height="auto"))},[n,i,a]),u=o=>{o.key==="Enter"&&!o.shiftKey&&(o.preventDefault(),f())},p=o=>{l(o.target.value);const b=o.target;b.style.height="auto",b.style.height=`${Math.min(b.scrollHeight,120)}px`};return r.jsxs("div",{className:"flex items-end gap-2 px-3 py-2.5 shrink-0",style:{background:"var(--widget-composer-bg, #ffffff)",borderTop:"1px solid var(--widget-border, rgba(0,0,0,0.08))"},children:[r.jsxs("div",{className:"flex-1 relative",children:[r.jsx("textarea",{ref:d,value:n,onChange:p,onKeyDown:u,placeholder:g,disabled:i,maxLength:c+50,rows:1,className:"w-full resize-none text-sm leading-relaxed rounded-xl px-3.5 py-2 outline-none disabled:opacity-50",style:{background:"var(--widget-input-bg, #f3f4f6)",color:t?"var(--danger, #ef4444)":"var(--widget-text, #1f2937)",maxHeight:"120px",border:`1px solid ${t?"var(--danger, #ef4444)":"var(--widget-input-border, transparent)"}`},"aria-label":"訊息輸入"}),n.length>=c*.8&&r.jsxs("span",{className:"absolute right-2 bottom-1 text-[10px]",style:{color:t?"var(--danger, #ef4444)":"var(--widget-text-dim, #9ca3af)"},children:[n.length,"/",c]})]}),r.jsx("button",{type:"button",onClick:f,disabled:!e,className:"w-9 h-9 rounded-full flex items-center justify-center shrink-0 transition-opacity disabled:opacity-30",style:{background:e?"var(--widget-primary, var(--ds-color-primary))":"var(--widget-send-disabled, #d1d5db)",color:"#ffffff"},"aria-label":"送出訊息",children:r.jsxs("svg",{width:"18",height:"18",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"2",strokeLinecap:"round",strokeLinejoin:"round","aria-hidden":"true",children:[r.jsx("line",{x1:"22",y1:"2",x2:"11",y2:"13"}),r.jsx("polygon",{points:"22 2 15 22 11 13 2 9 22 2"})]})})]})}export{w as W,k as a};
