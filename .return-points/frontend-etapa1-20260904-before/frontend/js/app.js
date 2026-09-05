import {localidades,sensores} from "./datos-demo.js?v=6";
import {fetchHistorialEducativo,fetchUltimasEducativas} from "./api.js?v=7";
import {svgGrafico,svgGraficoAltura,svgGraficoTemperaturaAgua,svgGraficoTemperaturas} from "./graficos.js?v=5";

let localidad="colchane",colegioId=null,sensorActivo="temperatura_aire",categoriaActiva="temperatura",periodo="7d",dashboard={items:[]},historiales={},estadosHistorial={},cicloCarga=0;
const horasPeriodo={"24h":24,"7d":168,"30d":720};
const grupos={
 temperatura:{titulo:"TEMPERATURA",icono:"🌡️",color:"#ee5918",claves:["temperatura_aire","temperatura_tierra","temperatura_bajo_tierra","temperatura_agua"],botones:["Aire","Tierra","Bajo tierra","Agua"]},
 humedad:{titulo:"HUMEDAD",icono:"💧",color:"#1388c4",claves:["humedad_aire","humedad_tierra","humedad_hojas"],botones:["☁️","💧","🍃"]},
 crecimiento:{titulo:"CRECIMIENTO",icono:"🌱",color:"#62a72c",claves:["altura_planta"],botones:["Altura promedio"]},
 agua:{titulo:"CALIDAD DEL AGUA",icono:"💧",color:"#7d3b96",claves:["ph_agua","sales_agua"],botones:["pH","SAL"]}
};
const categorias={temperatura:{etiqueta:"Temperatura",icono:"🌡️"},humedad:{etiqueta:"Humedad",icono:"💧"},crecimiento:{etiqueta:"Crecimiento",icono:"🌱"},agua:{etiqueta:"Calidad del agua",icono:"🧪"}};
const modos={temperatura:"temperatura_aire",humedad:"all",crecimiento:"altura_planta",agua:"ph_agua"};
const $=selector=>document.querySelector(selector);
const clavesEducativas=Object.keys(sensores);
const itemsResumen=()=>Array.isArray(dashboard?.items)?dashboard.items:[];
const variable=clave=>itemsResumen().find(item=>item.variable===clave)||null;
const convertirValor=(clave,valor,unidades)=>clave==="humedad_tierra"&&unidades==="m³/m³"?Number(valor)*100:Number(valor);
const unidadVisible=(clave,unidad)=>clave==="humedad_tierra"&&unidad==="m³/m³"?"%":unidad||sensores[clave]?.unidad||"";
const colegioActual=()=>localidades[localidad].colegio;

function estadoInicial(estado="cargando"){
 return {items:clavesEducativas.map(clave=>({variable:clave,nombre:sensores[clave].nombre,valor:null,unidad:sensores[clave].unidad,estado,fuente:null,colegio_id:null}))};
}
function valoresHistorial(clave){
 const historial=historiales[clave];
 return (historial?.items||[]).map(item=>convertirValor(clave,item?.value,historial?.unidad)).filter(Number.isFinite);
}
function puntosHistorial(clave){
 const historial=historiales[clave];
 return (historial?.items||[]).map(item=>{const valor=convertirValor(clave,item?.value,historial?.unidad),timestamp=Number(item?.timestamp_utc)*1000||Date.parse(item?.datetime);return {valor,timestamp,etiqueta:item?.datetime||new Date(timestamp).toISOString()}}).filter(item=>Number.isFinite(item.valor)&&Number.isFinite(item.timestamp));
}
function crearLocalidades(){
 $("#localidades").innerHTML=Object.entries(localidades).map(([clave,item])=>'<button data-localidad="'+clave+'" class="'+(clave===localidad?"active":"")+'" aria-pressed="'+(clave===localidad)+'"><span class="locality-icon">'+item.icono+'</span><span><b>'+item.nombre+'</b><small>'+item.colegio+'</small></span><em>'+item.tipo+'</em></button>').join("");
 document.querySelectorAll("[data-localidad]").forEach(button=>button.onclick=()=>seleccionarLocalidad(button.dataset.localidad));
}
function crearCategorias(){
 $("#research-categories").innerHTML=Object.entries(categorias).map(([clave,item])=>'<button type="button" data-categoria="'+clave+'" class="'+(clave===categoriaActiva?"active":"")+'" style="--category-color:'+grupos[clave].color+'" aria-controls="grafico-'+clave+'" aria-pressed="'+(clave===categoriaActiva)+'"><span>'+item.icono+'</span><b>'+item.etiqueta+'</b></button>').join("");
 document.querySelectorAll("[data-categoria]").forEach(button=>button.onclick=()=>seleccionarCategoria(button.dataset.categoria));
}
function crearHotspots(){
 $("#hotspots").innerHTML=Object.entries(sensores).filter(([,sensor])=>sensor.hotspot).map(([clave,sensor])=>'<button class="hotspot '+sensor.hotspot+(clave===sensorActivo?" selected":"")+'" data-sensor="'+clave+'" aria-label="Explorar '+sensor.nombre+'"></button>').join("");
 document.querySelectorAll("[data-sensor]").forEach(button=>button.onclick=()=>{sensorActivo=button.dataset.sensor;actualizar()});
}
function detalle(){
 const sensor=sensores[sensorActivo],lectura=variable(sensorActivo)||{estado:"cargando"},estado=lectura.estado||"cargando",esReal=estado==="ok"&&Number.isFinite(Number(lectura.valor));
 const textos={cargando:["● Cargando medición","Cargando..."],sin_asociacion:["● Sin sensor asociado","Sin asociación"],sin_datos:["● Sensor sin mediciones","Sin datos"],no_disponible:["● Medición no disponible","No disponible"]};
 const [textoEstado,textoValor]=esReal?["● Dato real del sensor",convertirValor(sensorActivo,lectura.valor,lectura.unidad).toLocaleString("es-CL",{maximumFractionDigits:2})]:(textos[estado]||textos.no_disponible);
 $("#detail-card").style.setProperty("--accent",sensor.color);$("#detail-icon").textContent=sensor.icono;$("#detail-name").textContent=sensor.nombre;$("#detail-meaning").textContent=sensor.texto;$("#detail-card .status").textContent=textoEstado;$("#detail-school").textContent="📍 "+colegioActual()+" · "+localidades[localidad].nombre;$("#detail-value").textContent=textoValor;$("#detail-unit").textContent=esReal?unidadVisible(sensorActivo,lectura.unidad):"";$("#detail-range").textContent=sensor.rango;
}
function actualizarCartelTemperaturaAgua(){
 const cartel=$("#water-temperature-sign"),valor=$("#water-temperature-value"),fecha=$("#water-temperature-date"),lectura=variable("temperatura_agua")||{estado:"cargando"};
 const clase=lectura.estado==="ok"?"ok":lectura.estado==="cargando"?"loading":lectura.estado==="no_disponible"?"error":"empty";cartel.classList.remove("loading","empty","error","ok");cartel.classList.add(clase);
 if(clase==="loading"){valor.textContent="Cargando...";fecha.textContent="";return}if(clase==="error"){valor.textContent="No disponible";fecha.textContent="";return}if(clase==="empty"){valor.textContent=lectura.estado==="sin_asociacion"?"Sin equipo asociado":"Sin medición de agua";fecha.textContent="";return}
 valor.textContent=Number(lectura.valor).toLocaleString("es-CL",{minimumFractionDigits:1,maximumFractionDigits:1})+" °C";fecha.textContent=lectura.datetime_local?"Última: "+String(lectura.datetime_local).slice(0,10).split("-").reverse().join("/"):"";
}
function clavesGrupo(nombre){const grupo=grupos[nombre],modo=modos[nombre];return modo==="all"||nombre==="temperatura"&&modo==="temperatura_todas"?grupo.claves:[modo]}
function seriesGrupo(nombre){return clavesGrupo(nombre).map(clave=>({valores:valoresHistorial(clave),color:sensores[clave].color}))}
function estadoGrafico(nombre){
 const claves=clavesGrupo(nombre),estados=claves.map(clave=>estadosHistorial[clave]||"cargando"),disponibles=claves.filter(clave=>valoresHistorial(clave).length);
 if(estados.includes("cargando"))return {tipo:"cargando",texto:"Cargando historial real…"};
 if(disponibles.length)return {tipo:"ok",texto:"Historial real · "+horasPeriodo[periodo]+" horas"};
 if(estados.includes("no_disponible"))return {tipo:"error",texto:"No fue posible cargar el historial"};
 if(estados.includes("sin_asociacion"))return {tipo:"vacio",texto:"Esta variable aún no tiene un sensor asociado"};
 return {tipo:"vacio",texto:"El sensor asociado no tiene mediciones en este periodo"};
}
function tarjetaCrecimiento(grupo){
 const historial=historiales.altura_planta,items=(historial?.items||[]).map(item=>({fecha:String(item.datetime).slice(0,10),altura_promedio_cm:Number(item.value),plantas_medidas:item.plantas_medidas||0})),ultimo=items.at(-1),estado=estadoGrafico("crecimiento");
 const resumen=ultimo?'<div class="growth-summary"><div><small>Último promedio</small><strong>'+ultimo.altura_promedio_cm.toLocaleString("es-CL",{maximumFractionDigits:2})+' <span>cm</span></strong></div><div><small>Fecha de última medición</small><b>'+ultimo.fecha+'</b></div><div><small>Plantas medidas</small><b>'+ultimo.plantas_medidas+'</b></div></div>':"";
 const grafico=items.length?svgGraficoAltura(items):'<div class="growth-empty">'+estado.texto+'</div>';
 return '<article id="grafico-crecimiento" class="chart-card growth-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls"><button class="active growth-only" type="button" aria-pressed="true">Altura promedio</button><span>cm</span></div></header><h3>Altura promedio de las plantas</h3><div class="chart-state '+estado.tipo+'">'+estado.texto+'</div>'+resumen+'<div class="chart-wrap">'+grafico+'</div></article>';
}
function tarjetaTemperaturaAgua(grupo,controles){
 const historial=historiales.temperatura_agua,items=(historial?.items||[]).map(item=>({fecha:String(item.datetime).slice(0,10),valor:Number(item.value)})),estado=estadoGrafico("temperatura"),grafico=items.length?svgGraficoTemperaturaAgua(items):'<div class="growth-empty">'+estado.texto+'</div>';
 return '<article id="grafico-temperatura" class="chart-card water-temperature-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls temperature-controls">'+controles+'<span>°C</span></div></header><h3>Temperatura del agua del estanque</h3><div class="chart-state '+estado.tipo+'">'+estado.texto+'</div><div class="chart-wrap">'+grafico+'</div></article>';
}
function tarjetaTemperaturas(grupo,controles){
 const nombres={temperatura_aire:"Aire",temperatura_tierra:"Tierra",temperatura_bajo_tierra:"Bajo tierra",temperatura_agua:"Agua"},series=grupos.temperatura.claves.map(clave=>({clave,nombre:nombres[clave],color:sensores[clave].color,puntos:puntosHistorial(clave)})),tieneDatos=series.some(serie=>serie.puntos.length),faltantes=series.filter(serie=>!serie.puntos.length).map(serie=>serie.nombre),cargando=series.some(serie=>(estadosHistorial[serie.clave]||"cargando")==="cargando");
 const estado=cargando?{tipo:"cargando",texto:"Cargando temperaturas del huerto…"}:!tieneDatos?{tipo:"vacio",texto:"No hay temperaturas disponibles en este periodo"}:faltantes.length?{tipo:"vacio",texto:"Sin datos disponibles: "+faltantes.join(", ")}:{tipo:"ok",texto:"Comparación de las temperaturas disponibles"};
 const leyenda='<div class="temperature-legend">'+series.map(serie=>'<span class="'+(!serie.puntos.length?"missing":"")+'"><i style="--series-color:'+serie.color+'"></i>'+serie.nombre+'</span>').join("")+'</div>',grafico=tieneDatos?svgGraficoTemperaturas(series):'<div class="growth-empty">'+estado.texto+'</div>';
 return '<article id="grafico-temperatura" class="chart-card all-temperatures-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls temperature-controls">'+controles+'<span>°C</span></div></header><h3>Comparación de temperaturas del huerto</h3><div class="chart-state '+estado.tipo+'">'+estado.texto+'</div>'+leyenda+'<div class="chart-wrap">'+grafico+'</div></article>';
}
function crearGraficos(){
 $("#charts").innerHTML=Object.entries(grupos).map(([nombre,grupo])=>{if(nombre==="crecimiento")return tarjetaCrecimiento(grupo);const modo=modos[nombre],todas=nombre==="temperatura"&&modo==="temperatura_todas",base=sensores[modo==="all"||todas?grupo.claves[0]:modo],estado=estadoGrafico(nombre),controles=grupo.claves.map((clave,indice)=>'<button data-grupo="'+nombre+'" data-modo="'+clave+'" class="'+(modo===clave?"active":"")+'" title="'+(sensores[clave].nombreCompleto||sensores[clave].nombre)+'">'+grupo.botones[indice]+'</button>').join("")+(nombre==="temperatura"?'<button data-grupo="temperatura" data-modo="temperatura_todas" class="'+(modo==="temperatura_todas"?"active":"")+'" title="Todas las temperaturas">Todas</button>':nombre!=="agua"?'<button data-grupo="'+nombre+'" data-modo="all" class="'+(modo==="all"?"active":"")+'" title="Comparar">📈</button>':"");if(nombre==="temperatura"&&modo==="temperatura_agua")return tarjetaTemperaturaAgua(grupo,controles);if(todas)return tarjetaTemperaturas(grupo,controles);const series=seriesGrupo(nombre),tieneDatos=series.some(serie=>serie.valores.length),grafico=tieneDatos?svgGrafico(series,periodo,base.min,base.max,modo==="all"?null:base.ideal,nombre==="temperatura"?"°":nombre==="humedad"?"%":""):'<div class="growth-empty">'+estado.texto+'</div>',subtitulo=nombre==="temperatura"?'<h3 class="temperature-variable-title">'+base.nombre+'</h3>':"";return '<article id="grafico-'+nombre+'" class="chart-card" style="--accent:'+grupo.color+'"><div class="chart-school">📍 '+colegioActual()+'</div><header><div>'+grupo.icono+' <b>'+grupo.titulo+'</b></div><div class="chart-controls '+(nombre==="temperatura"?"temperature-controls":"")+'">'+controles+'<span>'+base.unidad+'</span></div></header>'+subtitulo+'<div class="chart-state '+estado.tipo+'">'+estado.texto+'</div><div class="chart-wrap">'+grafico+'</div></article>'}).join("");
 document.querySelectorAll("[data-modo]").forEach(button=>button.onclick=()=>seleccionarModo(button.dataset.grupo,button.dataset.modo));
}
function actualizar(){const loc=localidades[localidad];$("#explore-label").textContent="🔎 Exploración en vivo · "+loc.nombre;$("#school-context").textContent="📍 "+colegioActual();$("#history-label").textContent="▦ Historial del huerto · "+loc.nombre;$("#history-school").textContent="📍 "+colegioActual()+" · Compara los periodos y descubre cómo responde nuestra planta.";crearLocalidades();crearCategorias();crearHotspots();actualizarCartelTemperaturaAgua();detalle();crearGraficos()}
async function cargarHistorialClaves(claves,ciclo){
 const consultas=[...new Set(claves)];consultas.forEach(clave=>estadosHistorial[clave]="cargando");crearGraficos();
 await Promise.all(consultas.map(async clave=>{try{const data=await fetchHistorialEducativo(localidad,clave,horasPeriodo[periodo],60);if(ciclo!==cicloCarga)return;historiales[clave]=data;estadosHistorial[clave]=data?.estado||"sin_datos"}catch{if(ciclo!==cicloCarga)return;historiales[clave]={items:[]};estadosHistorial[clave]="no_disponible"}}));if(ciclo===cicloCarga)crearGraficos();
}
function clavesGraficosVisibles(){return Object.keys(grupos).flatMap(clavesGrupo)}
function seleccionarCategoria(categoria){categoriaActiva=categoria;crearCategorias();document.getElementById("grafico-"+categoria)?.scrollIntoView({behavior:"smooth",block:"start"})}
async function seleccionarModo(grupo,modo){modos[grupo]=modo;crearGraficos();await cargarHistorialClaves(clavesGrupo(grupo),cicloCarga)}
async function cargar(){
 const ciclo=++cicloCarga;dashboard=estadoInicial();colegioId=null;historiales={};estadosHistorial={};document.querySelectorAll(".refresh").forEach(button=>{button.disabled=true;button.textContent="Actualizando…"});$("#source").textContent="● Cargando datos reales…";actualizar();
 try{const data=await fetchUltimasEducativas(localidad);if(ciclo!==cicloCarga)return;dashboard=data||estadoInicial("no_disponible");colegioId=dashboard.items?.find(item=>item.colegio_id)?.colegio_id||null;const reales=dashboard.items?.filter(item=>item.estado==="ok").length||0;$("#source").textContent=reales?"● Conectado a FastAPI · "+reales+" mediciones reales":"● Conectado a FastAPI · sin mediciones disponibles"}
 catch{if(ciclo!==cicloCarga)return;dashboard=estadoInicial("no_disponible");$("#source").textContent="● FastAPI no disponible"}
 finally{if(ciclo===cicloCarga){actualizar();await cargarHistorialClaves(clavesGraficosVisibles(),ciclo);document.querySelectorAll(".refresh").forEach(button=>{button.disabled=false;button.textContent="↻ Actualizar datos"})}}
}
function seleccionarLocalidad(clave){localidad=clave;colegioId=null;dashboard=estadoInicial();historiales={};estadosHistorial={};actualizar();cargar()}
document.querySelectorAll(".refresh").forEach(button=>button.onclick=cargar);
$("#water-temperature-sign").onclick=async()=>{categoriaActiva="temperatura";modos.temperatura="temperatura_agua";crearCategorias();crearGraficos();document.getElementById("grafico-temperatura")?.scrollIntoView({behavior:"smooth",block:"start"});await cargarHistorialClaves(["temperatura_agua"],cicloCarga)};
document.querySelectorAll("[data-period]").forEach(button=>button.onclick=async()=>{periodo=button.dataset.period;document.querySelectorAll("[data-period]").forEach(item=>item.classList.toggle("active",item===button));const ciclo=++cicloCarga;historiales={};estadosHistorial={};actualizar();await cargarHistorialClaves(clavesGraficosVisibles(),ciclo)});
dashboard=estadoInicial();actualizar();cargar();
