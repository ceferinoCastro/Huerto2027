function trazadoSuave(puntos){
 if(!puntos.length)return "";
 if(puntos.length===1)return 'M'+puntos[0].x+','+puntos[0].y;
 let d='M'+puntos[0].x+','+puntos[0].y;
 for(let i=0;i<puntos.length-1;i++){
  const p0=puntos[i-1]||puntos[i],p1=puntos[i],p2=puntos[i+1],p3=puntos[i+2]||p2;
  const cp1x=p1.x+(p2.x-p0.x)/6,cp1y=p1.y+(p2.y-p0.y)/6,cp2x=p2.x-(p3.x-p1.x)/6,cp2y=p2.y-(p3.y-p1.y)/6;
  d+=' C'+cp1x+','+cp1y+' '+cp2x+','+cp2y+' '+p2.x+','+p2.y;
 }
 return d;
}
export function svgGrafico(series,period,min,max,ideal,unidad){
 const ventanaMs=duracionPeriodoMs[period]||duracionPeriodoMs["7d"];
 const ahora=Date.now(),limiteTiempoMin=ahora-ventanaMs,limiteTiempoMax=ahora,spanTiempo=limiteTiempoMax-limiteTiempoMin||1;
 const filtroReciente=punto=>Number.isFinite(punto.valor)&&Number.isFinite(punto.timestamp)&&punto.timestamp>0&&punto.timestamp>=limiteTiempoMin&&punto.timestamp<=limiteTiempoMax;
 const puntos=series.flatMap(s=>s.puntos).filter(filtroReciente);
 const valores=puntos.map(punto=>punto.valor);
 let limiteMin,limiteMax;
 if(valores.length){
  const dataMin=Math.min(...valores),dataMax=Math.max(...valores),spanDatos=dataMax-dataMin||Math.abs(dataMax)||1,margen=spanDatos*0.1;
  limiteMin=dataMin-margen;limiteMax=dataMax+margen;
 }else{
  const cotas=[min,max,ideal?.[0],ideal?.[1]].filter(Number.isFinite);
  limiteMin=cotas.length?Math.min(...cotas):0;limiteMax=cotas.length?Math.max(...cotas):1;
 }
 const span=limiteMax-limiteMin||1;
 const y=v=>190-((v-limiteMin)/span)*145;
 const x=timestamp=>68+(timestamp-limiteTiempoMin)*(617/spanTiempo);
 let html='<svg viewBox="0 0 740 235" role="img" aria-label="Gráfico histórico">';
 if(ideal&&Number.isFinite(ideal[0])&&Number.isFinite(ideal[1])){
  const yIdealTop=Math.max(45,Math.min(190,y(ideal[1]))),yIdealBottom=Math.max(45,Math.min(190,y(ideal[0])));
  html+='<rect x="68" y="45" width="617" height="145" fill="#f8d7da"/>';
  html+='<rect x="68" y="'+yIdealTop+'" width="617" height="'+(yIdealBottom-yIdealTop)+'" fill="#d4edda"/>';
 }
 [0,.25,.5,.75,1].forEach(p=>{const v=limiteMax-span*p,py=45+145*p;html+='<line x1="68" x2="685" y1="'+py+'" y2="'+py+'" class="grid-line"/><text x="59" y="'+(py+5)+'" text-anchor="end">'+(Number.isInteger(v)?v:v.toFixed(1))+(unidad||"")+'</text>'});
 series.forEach(s=>{
  const ordenados=s.puntos.filter(filtroReciente).sort((a,b)=>a.timestamp-b.timestamp),total=ordenados.length,puntosXY=ordenados.map(punto=>({x:x(punto.timestamp),y:y(punto.valor)}));
  if(total>1)html+='<path d="'+trazadoSuave(puntosXY)+'" fill="none" stroke="'+s.color+'" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>';
 });
 const DIVISIONES=6;
 Array.from({length:DIVISIONES+1},(_,indice)=>indice/DIVISIONES).forEach(proporcion=>{const timestamp=limiteTiempoMin+spanTiempo*proporcion;html+='<text x="'+x(timestamp)+'" y="222" text-anchor="middle">'+etiquetaTiempo(timestamp,period)+'</text>'});
 return html+"</svg>";
}

export function svgGraficoCrecimiento(items,campo,tituloEje){
 const width=740,height=260,left=82,right=28,top=28,bottom=55;
 const valores=items.map(item=>Number(item[campo]));
 const dataMin=Math.min(...valores),dataMax=Math.max(...valores),spanDatos=dataMax-dataMin||Math.abs(dataMax)||1,margen=spanDatos*0.1;
 const limiteMin=dataMin-margen,limiteMax=dataMax+margen,span=limiteMax-limiteMin||1;
 const x=(indice,total)=>total<=1?(left+width-right)/2:left+indice*((width-left-right)/(total-1));
 const y=valor=>top+(limiteMax-valor)*((height-top-bottom)/span);
 const puntosXY=items.map((item,indice)=>({x:x(indice,items.length),y:y(Number(item[campo]))}));
 let html='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="'+tituloEje+' diario de las plantas, fechas en el eje horizontal y centímetros en el eje vertical">';
 [0,.25,.5,.75,1].forEach(proporcion=>{const valor=limiteMax-span*proporcion,posY=top+proporcion*(height-top-bottom);html+='<line x1="'+left+'" x2="'+(width-right)+'" y1="'+posY+'" y2="'+posY+'" class="grid-line"/><text x="'+(left-10)+'" y="'+(posY+5)+'" text-anchor="end">'+valor.toLocaleString("es-CL",{maximumFractionDigits:1})+'</text>'});
 html+='<text class="axis-title" x="18" y="'+((top+height-bottom)/2)+'" text-anchor="middle" transform="rotate(-90 18 '+((top+height-bottom)/2)+')">'+tituloEje+' (cm)</text>';
 html+='<path class="growth-line" d="'+trazadoSuave(puntosXY)+'" fill="none" stroke-linecap="round" stroke-linejoin="round"/>';
 const paso=Math.max(1,Math.ceil(items.length/6));items.forEach((item,indice)=>{if(indice%paso===0||indice===items.length-1)html+='<text x="'+x(indice,items.length)+'" y="'+(height-22)+'" text-anchor="middle">'+item.fecha.slice(8,10)+'/'+item.fecha.slice(5,7)+'</text>'});
 html+='<text class="axis-title" x="'+((left+width-right)/2)+'" y="'+(height-3)+'" text-anchor="middle">Fecha</text>';
 return html+'</svg>';
}

export function svgGraficoTemperaturaAgua(items){
 const width=740,height=260,left=82,right=28,top=28,bottom=55;
 const valores=items.map(item=>Number(item.valor));
 const dataMin=Math.min(...valores),dataMax=Math.max(...valores),spanDatos=dataMax-dataMin||Math.abs(dataMax)||1,margen=spanDatos*0.1;
 const limiteMin=dataMin-margen,limiteMax=dataMax+margen;
 const x=(indice,total)=>total<=1?(left+width-right)/2:left+indice*((width-left-right)/(total-1));
 const y=valor=>top+(limiteMax-valor)*((height-top-bottom)/(limiteMax-limiteMin));
 const puntosXY=items.map((item,indice)=>({x:x(indice,items.length),y:y(Number(item.valor))}));
 let html='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Temperatura promedio diaria del agua, fechas en el eje horizontal y grados Celsius en el eje vertical">';
 [0,.25,.5,.75,1].forEach(proporcion=>{const valor=limiteMax-(limiteMax-limiteMin)*proporcion,posY=top+proporcion*(height-top-bottom);html+='<line x1="'+left+'" x2="'+(width-right)+'" y1="'+posY+'" y2="'+posY+'" class="grid-line"/><text x="'+(left-10)+'" y="'+(posY+5)+'" text-anchor="end">'+valor.toLocaleString("es-CL",{maximumFractionDigits:1})+'</text>'});
 html+='<text class="axis-title water-axis" x="18" y="'+((top+height-bottom)/2)+'" text-anchor="middle" transform="rotate(-90 18 '+((top+height-bottom)/2)+')">Temperatura promedio (°C)</text>';
 html+='<path class="water-temperature-line" d="'+trazadoSuave(puntosXY)+'" fill="none" stroke-linecap="round" stroke-linejoin="round"/>';
 const paso=Math.max(1,Math.ceil(items.length/6));items.forEach((item,indice)=>{if(indice%paso===0||indice===items.length-1)html+='<text x="'+x(indice,items.length)+'" y="'+(height-22)+'" text-anchor="middle">'+item.fecha.slice(8,10)+'/'+item.fecha.slice(5,7)+'</text>'});
 html+='<text class="axis-title water-axis" x="'+((left+width-right)/2)+'" y="'+(height-3)+'" text-anchor="middle">Fecha</text>';
 return html+'</svg>';
}

const duracionPeriodoMs={"24h":24*3600*1000,"7d":7*24*3600*1000,"30d":30*24*3600*1000};
function etiquetaTiempo(timestamp,period){
 const fecha=new Date(timestamp);
 return period==="24h"?String(fecha.getUTCHours()).padStart(2,"0")+":"+String(fecha.getUTCMinutes()).padStart(2,"0"):String(fecha.getUTCDate()).padStart(2,"0")+"/"+String(fecha.getUTCMonth()+1).padStart(2,"0");
}
export function svgGraficoTemperaturas(series,period){
 const width=740,height=280,left=82,right=28,top=28,bottom=64;
 const ventanaMs=duracionPeriodoMs[period]||duracionPeriodoMs["7d"];
 const ahora=Date.now(),limiteTiempoMin=ahora-ventanaMs,limiteTiempoMax=ahora;
 const filtroReciente=punto=>Number.isFinite(punto.valor)&&Number.isFinite(punto.timestamp)&&punto.timestamp>0&&punto.timestamp>=limiteTiempoMin&&punto.timestamp<=limiteTiempoMax;
 const puntos=series.flatMap(serie=>serie.puntos).filter(filtroReciente);
 if(!puntos.length)return "";
 const valores=puntos.map(punto=>punto.valor);
 const minimoDato=Math.min(...valores),maximoDato=Math.max(...valores),spanDatos=maximoDato-minimoDato||Math.abs(maximoDato)||1,margen=spanDatos*0.1;
 const limiteMin=minimoDato-margen,limiteMax=maximoDato+margen;
 const spanTiempo=limiteTiempoMax-limiteTiempoMin||1;
 const x=timestamp=>left+(timestamp-limiteTiempoMin)*((width-left-right)/spanTiempo);
 const y=valor=>top+(limiteMax-valor)*((height-top-bottom)/(limiteMax-limiteMin));
 let html='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Comparación por fecha de las temperaturas del aire, bajo tierra y agua en grados Celsius">';
 [0,.25,.5,.75,1].forEach(proporcion=>{const valor=limiteMax-(limiteMax-limiteMin)*proporcion,posY=top+proporcion*(height-top-bottom);html+='<line x1="'+left+'" x2="'+(width-right)+'" y1="'+posY+'" y2="'+posY+'" class="grid-line"/><text x="'+(left-10)+'" y="'+(posY+5)+'" text-anchor="end">'+valor.toLocaleString("es-CL",{maximumFractionDigits:1})+'</text>'});
 html+='<text class="axis-title temperature-axis" x="18" y="'+((top+height-bottom)/2)+'" text-anchor="middle" transform="rotate(-90 18 '+((top+height-bottom)/2)+')">Temperatura (°C)</text>';
 series.forEach(serie=>{const ordenados=serie.puntos.filter(filtroReciente).sort((a,b)=>a.timestamp-b.timestamp),puntosXY=ordenados.map(punto=>({x:x(punto.timestamp),y:y(punto.valor)}));if(ordenados.length>1)html+='<path d="'+trazadoSuave(puntosXY)+'" fill="none" stroke="'+serie.color+'" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'});
 const DIVISIONES=6;
 Array.from({length:DIVISIONES+1},(_,indice)=>indice/DIVISIONES).forEach(proporcion=>{const timestamp=limiteTiempoMin+spanTiempo*proporcion;html+='<text x="'+x(timestamp)+'" y="'+(height-28)+'" text-anchor="middle">'+etiquetaTiempo(timestamp,period)+'</text>'});
 html+='<text class="axis-title temperature-axis" x="'+((left+width-right)/2)+'" y="'+(height-4)+'" text-anchor="middle">Fecha</text>';
 return html+'</svg>';
}
