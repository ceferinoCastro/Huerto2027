const etiquetas={"24h":["00","04","08","12","16","20","Ahora"],"7d":["Lun","Mar","Mié","Jue","Vie","Sáb","Hoy"],"30d":["1","5","10","15","20","25","30"]};

export function svgGrafico(series,period,min,max,ideal,unidad){
 const y=v=>190-((v-min)/(max-min))*145;
 const x=(indice,total)=>total<=1?380:75+indice*(610/(total-1));
 let html='<svg viewBox="0 0 740 235" role="img" aria-label="Gráfico histórico">';
 if(ideal){html+='<rect x="68" y="45" width="617" height="145" fill="#f5b4aa" opacity=".68"/><rect x="68" y="'+y(ideal[1])+'" width="617" height="'+(y(ideal[0])-y(ideal[1]))+'" fill="#dcecb5"/>'}
 [0,.25,.5,.75,1].forEach(p=>{const v=max-(max-min)*p,py=45+145*p;html+='<line x1="68" x2="685" y1="'+py+'" y2="'+py+'" class="grid-line"/><text x="59" y="'+(py+5)+'" text-anchor="end">'+(Number.isInteger(v)?v:v.toFixed(1))+(unidad||"")+'</text>'});
 series.forEach(s=>{
  const total=s.valores.length,pts=s.valores.map((v,i)=>x(i,total)+","+y(v)).join(" ");
  html+='<polyline points="'+pts+'" fill="none" stroke="'+s.color+'" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>';
  s.valores.forEach((v,i)=>html+='<circle cx="'+x(i,total)+'" cy="'+y(v)+'" r="'+(total>20?"3":"7")+'" fill="'+s.color+'" stroke="#fff9e8" stroke-width="'+(total>20?"1.5":"4")+'"/>');
 });
 etiquetas[period].forEach((l,i)=>html+='<text x="'+x(i,etiquetas[period].length)+'" y="222" text-anchor="middle">'+l+'</text>');
 return html+"</svg>";
}

export function svgGraficoAltura(items){
 const width=740,height=260,left=82,right=28,top=28,bottom=55;
 const valores=items.map(item=>Number(item.altura_promedio_cm));
 const maximo=Math.max(...valores),limite=Math.max(5,Math.ceil((maximo*1.15)/5)*5);
 const x=(indice,total)=>total<=1?(left+width-right)/2:left+indice*((width-left-right)/(total-1));
 const y=valor=>top+(limite-valor)*((height-top-bottom)/limite);
 const puntos=items.map((item,indice)=>x(indice,items.length)+","+y(Number(item.altura_promedio_cm))).join(" ");
 let html='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Altura promedio diaria de las plantas, fechas en el eje horizontal y centímetros en el eje vertical">';
 [0,.25,.5,.75,1].forEach(proporcion=>{const valor=limite*(1-proporcion),posY=top+proporcion*(height-top-bottom);html+='<line x1="'+left+'" x2="'+(width-right)+'" y1="'+posY+'" y2="'+posY+'" class="grid-line"/><text x="'+(left-10)+'" y="'+(posY+5)+'" text-anchor="end">'+valor.toLocaleString("es-CL",{maximumFractionDigits:1})+'</text>'});
 html+='<text class="axis-title" x="18" y="'+((top+height-bottom)/2)+'" text-anchor="middle" transform="rotate(-90 18 '+((top+height-bottom)/2)+')">Altura promedio (cm)</text>';
 html+='<polyline class="growth-line" points="'+puntos+'"/>';
 items.forEach((item,indice)=>{const valor=Number(item.altura_promedio_cm);html+='<circle class="growth-point" cx="'+x(indice,items.length)+'" cy="'+y(valor)+'" r="6"><title>'+item.fecha+': '+valor.toLocaleString("es-CL")+' cm · '+item.plantas_medidas+' plantas</title></circle>'});
 const paso=Math.max(1,Math.ceil(items.length/6));items.forEach((item,indice)=>{if(indice%paso===0||indice===items.length-1)html+='<text x="'+x(indice,items.length)+'" y="'+(height-22)+'" text-anchor="middle">'+item.fecha.slice(8,10)+'/'+item.fecha.slice(5,7)+'</text>'});
 html+='<text class="axis-title" x="'+((left+width-right)/2)+'" y="'+(height-3)+'" text-anchor="middle">Fecha</text>';
 return html+'</svg>';
}

export function svgGraficoTemperaturaAgua(items){
 const width=740,height=260,left=82,right=28,top=28,bottom=55;
 const valores=items.map(item=>Number(item.valor));
 const minimoDato=Math.min(...valores),maximoDato=Math.max(...valores);
 const minimo=Math.floor(minimoDato-2),maximo=Math.ceil(maximoDato+2);
 const limiteMin=minimo===maximo?minimo-1:minimo,limiteMax=minimo===maximo?maximo+1:maximo;
 const x=(indice,total)=>total<=1?(left+width-right)/2:left+indice*((width-left-right)/(total-1));
 const y=valor=>top+(limiteMax-valor)*((height-top-bottom)/(limiteMax-limiteMin));
 const puntos=items.map((item,indice)=>x(indice,items.length)+","+y(Number(item.valor))).join(" ");
 let html='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Temperatura promedio diaria del agua, fechas en el eje horizontal y grados Celsius en el eje vertical">';
 [0,.25,.5,.75,1].forEach(proporcion=>{const valor=limiteMax-(limiteMax-limiteMin)*proporcion,posY=top+proporcion*(height-top-bottom);html+='<line x1="'+left+'" x2="'+(width-right)+'" y1="'+posY+'" y2="'+posY+'" class="grid-line"/><text x="'+(left-10)+'" y="'+(posY+5)+'" text-anchor="end">'+valor.toLocaleString("es-CL",{maximumFractionDigits:1})+'</text>'});
 html+='<text class="axis-title water-axis" x="18" y="'+((top+height-bottom)/2)+'" text-anchor="middle" transform="rotate(-90 18 '+((top+height-bottom)/2)+')">Temperatura promedio (°C)</text>';
 html+='<polyline class="water-temperature-line" points="'+puntos+'"/>';
 items.forEach((item,indice)=>{const valor=Number(item.valor);html+='<circle class="water-temperature-point" cx="'+x(indice,items.length)+'" cy="'+y(valor)+'" r="6"><title>'+item.fecha+': '+valor.toLocaleString("es-CL",{maximumFractionDigits:2})+' °C</title></circle>'});
 const paso=Math.max(1,Math.ceil(items.length/6));items.forEach((item,indice)=>{if(indice%paso===0||indice===items.length-1)html+='<text x="'+x(indice,items.length)+'" y="'+(height-22)+'" text-anchor="middle">'+item.fecha.slice(8,10)+'/'+item.fecha.slice(5,7)+'</text>'});
 html+='<text class="axis-title water-axis" x="'+((left+width-right)/2)+'" y="'+(height-3)+'" text-anchor="middle">Fecha</text>';
 return html+'</svg>';
}

export function svgGraficoTemperaturas(series){
 const width=740,height=280,left=82,right=28,top=28,bottom=64;
 const puntos=series.flatMap(serie=>serie.puntos).filter(punto=>Number.isFinite(punto.valor)&&Number.isFinite(punto.timestamp));
 if(!puntos.length)return "";
 const valores=puntos.map(punto=>punto.valor),fechas=puntos.map(punto=>punto.timestamp);
 const minimoDato=Math.min(...valores),maximoDato=Math.max(...valores);
 const limiteMin=Math.floor(minimoDato-2),limiteMax=Math.ceil(maximoDato+2);
 const fechaMin=Math.min(...fechas),fechaMax=Math.max(...fechas);
 const x=timestamp=>fechaMin===fechaMax?(left+width-right)/2:left+(timestamp-fechaMin)*((width-left-right)/(fechaMax-fechaMin));
 const y=valor=>top+(limiteMax-valor)*((height-top-bottom)/(limiteMax-limiteMin));
 let html='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Comparación por fecha de las temperaturas del aire, tierra, bajo tierra y agua en grados Celsius">';
 [0,.25,.5,.75,1].forEach(proporcion=>{const valor=limiteMax-(limiteMax-limiteMin)*proporcion,posY=top+proporcion*(height-top-bottom);html+='<line x1="'+left+'" x2="'+(width-right)+'" y1="'+posY+'" y2="'+posY+'" class="grid-line"/><text x="'+(left-10)+'" y="'+(posY+5)+'" text-anchor="end">'+valor.toLocaleString("es-CL",{maximumFractionDigits:1})+'</text>'});
 html+='<text class="axis-title temperature-axis" x="18" y="'+((top+height-bottom)/2)+'" text-anchor="middle" transform="rotate(-90 18 '+((top+height-bottom)/2)+')">Temperatura (°C)</text>';
 series.forEach(serie=>{const ordenados=[...serie.puntos].sort((a,b)=>a.timestamp-b.timestamp),linea=ordenados.map(punto=>x(punto.timestamp)+","+y(punto.valor)).join(" ");if(ordenados.length>1)html+='<polyline points="'+linea+'" fill="none" stroke="'+serie.color+'" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>';ordenados.forEach(punto=>{html+='<circle cx="'+x(punto.timestamp)+'" cy="'+y(punto.valor)+'" r="5" fill="'+serie.color+'" stroke="#fff9e8" stroke-width="3"><title>'+serie.nombre+' · '+punto.etiqueta+': '+punto.valor.toLocaleString("es-CL",{maximumFractionDigits:2})+' °C</title></circle>'})});
 const fechasUnicas=[...new Set(puntos.map(punto=>punto.timestamp))].sort((a,b)=>a-b),paso=Math.max(1,Math.ceil(fechasUnicas.length/6));fechasUnicas.forEach((timestamp,indice)=>{if(indice%paso===0||indice===fechasUnicas.length-1){const fecha=new Date(timestamp);html+='<text x="'+x(timestamp)+'" y="'+(height-28)+'" text-anchor="middle">'+String(fecha.getUTCDate()).padStart(2,"0")+'/'+String(fecha.getUTCMonth()+1).padStart(2,"0")+'</text>'}});
 html+='<text class="axis-title temperature-axis" x="'+((left+width-right)/2)+'" y="'+(height-4)+'" text-anchor="middle">Fecha</text>';
 return html+'</svg>';
}
