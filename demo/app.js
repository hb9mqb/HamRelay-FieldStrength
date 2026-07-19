const $ = id => document.getElementById(id);
const map = L.map("map", {preferCanvas:true}).setView([46.8,8.2], 8);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
}).addTo(map);
const markers = L.layerGroup().addTo(map);
let overlays = [], stations = [], sampleTimer;

async function json(url, options={}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}
const selectedIds = () => [...document.querySelectorAll('.station input:checked')].map(item=>item.value);

async function loadStations() {
  const query = new URLSearchParams();
  if ($("filterMode").value) query.set("mode", $("filterMode").value);
  if ($("filterBand").value) query.set("band", $("filterBand").value);
  if ($("filterCountry").value) query.set("country_code", $("filterCountry").value);
  const data = await json(`/v1/stations?${query}`); stations=data.items; markers.clearLayers();
  const coverage = await json("/v1/coverages");
  const calculated = new Set(coverage.items.map(item=>item.station_id));
  const previous = new Set(selectedIds());
  const autoSelected = previous.size ? null : stations.find(s=>calculated.has(s.station_id))?.station_id;
  $("stationList").replaceChildren();
  if(!stations.length) $("stationList").append(Object.assign(document.createElement("p"),{textContent:"No stations yet. Add the example below."}));
  stations.forEach(s=>{
    const label=document.createElement("label"); label.className="station";
    const input=document.createElement("input"); input.type="checkbox"; input.value=s.station_id; input.checked=previous.has(s.station_id)||s.station_id===autoSelected;
    const name=document.createElement("b"); name.textContent=s.station_id;
    const details=document.createElement("span"); details.textContent=`${s.mode??""} ${s.tx_frequency_mhz} MHz${calculated.has(s.station_id)?" · calculated":""}`;
    label.append(input,name,details); $("stationList").append(label);
  });
  stations.forEach(s=>L.marker([s.latitude_deg,s.longitude_deg]).bindPopup(`<b>${s.station_id}</b><br>${s.tx_frequency_mhz} MHz · ${s.erp_w} W ERP`).addTo(markers));
}

async function saveStation() {
  const id=$("stationId").value.trim();
  const record={station_id:id,name:$("stationName").value,latitude_deg:+$("latitude").value,longitude_deg:+$("longitude").value,coordinates_locked:$("coordinatesLocked").checked,coordinate_source:"demo editor",country_code:$("country").value,antenna_height_agl_m:+$("agl").value,tx_frequency_mhz:+$("frequency").value,mode:$("mode").value,band:$("band").value,polarization:"vertical",erp_w:+$("erp").value,status:"active",source:"demo editor"};
  await json(`/v1/stations/${encodeURIComponent(id)}`,{method:"PUT",headers:{"Content-Type":"application/json","X-API-Key":$("apiKey").value},body:JSON.stringify(record)});
  await loadStations();
}

async function calculateSelected() {
  const ids=selectedIds(); if(!ids.length) throw new Error("Select at least one station.");
  const formats=[]; if($("wantGeotiff").checked) formats.push("geotiff"); if($("wantTiles").checked) formats.push("tiles");
  if(!formats.length) throw new Error("Select at least one output format.");
  for(const id of ids){
    const body={station_id:id,radius_km:+$("radius").value,terrain_mode:$("terrainMode").value,output_formats:formats,geotiff_background:$("geotiffBackground").value,minimum_field_strength_dbuv_m:+$("threshold").value};
    if(body.terrain_mode==="dataset") body.dem_dataset_id=$("datasetId").value;
    const job=await json("/v1/calculations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    let state=job; while(["queued","running"].includes(state.status)){ $("jobStatus").textContent=JSON.stringify(state,null,2); await new Promise(r=>setTimeout(r,1500)); state=await json(`/v1/calculations/${job.job_id}`); }
    $("jobStatus").textContent=JSON.stringify(state,null,2); if(state.status!=="succeeded") throw new Error(state.error||"Calculation failed");
  }
  showOverlay(); updateDownloads();
}

function showOverlay(){
  const ids=selectedIds(); if(!ids.length) return;
  overlays.forEach(layer=>map.removeLayer(layer)); overlays=[];
  const threshold=+$("threshold").value, opacity=+$("opacity").value/100;
  const urls=$("composite").checked && ids.length>1
    ? [`/v1/composites/web-tiles/{z}/{x}/{y}.png?station_ids=${encodeURIComponent(ids.join(","))}&minimum_field_strength_dbuv_m=${threshold}&opacity=1`]
    : ids.map(id=>`/v1/coverage/${encodeURIComponent(id)}/web-tiles/{z}/{x}/{y}.png?minimum_field_strength_dbuv_m=${threshold}`);
  overlays=urls.map(url=>L.tileLayer(url,{opacity,maxZoom:18,noWrap:true}).addTo(map));
}

async function updateLegend(){
  const first=stations.find(s=>selectedIds().includes(s.station_id)); const data=await json(`/v1/legend?frequency_mhz=${first?.tx_frequency_mhz??439.5}`);
  $("legend").innerHTML=`<div><b>Field strength · dBµV/m</b></div><div class="gradient"></div><div class="ticks"><span>0</span><span>20</span><span>40</span><span>60</span><span>80</span><span>100</span></div><small>${data.expected_s_meter_reference.map(s=>`${s.label}: ${s.field_strength_dbuv_m}`).join(" · ")}</small>`;
}

function updateDownloads(){const id=selectedIds()[0]; for(const [element,path] of [[$("downloadRaw"),"field-strength.tif"],[$("downloadVisual"),"field-strength-visual.tif"]]){if(id){element.href=`/v1/coverage/${encodeURIComponent(id)}/${path}`;element.classList.remove("disabled")}else element.classList.add("disabled")}}

map.on("mousemove", event=>{clearTimeout(sampleTimer);sampleTimer=setTimeout(async()=>{const ids=selectedIds();if(!ids.length)return;try{const data=await json("/v1/samples",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({station_ids:ids,latitude_deg:event.latlng.lat,longitude_deg:event.latlng.lng})});const s=data.strongest;$("cursorSample").textContent=s?`${s.station_id}: ${s.field_strength_dbuv_m} dBµV/m · ${s.expected_s_meter} · ${s.expected_receiver_dbm} dBm`:"No calculated field here."}catch(error){$("cursorSample").textContent=error.message}},140)});

$("refreshStations").onclick=()=>loadStations().catch(showError); $("saveStation").onclick=()=>saveStation().catch(showError); $("calculate").onclick=()=>calculateSelected().catch(showError); $("showOverlay").onclick=()=>{showOverlay();updateLegend();updateDownloads()}; $("hideOverlay").onclick=()=>{overlays.forEach(layer=>map.removeLayer(layer));overlays=[]};
$("terrainMode").onchange=()=>$("datasetId").disabled=$("terrainMode").value!=="dataset";
$("radius").oninput=()=>$("radiusValue").value=`${$("radius").value} km`; $("threshold").oninput=()=>{$("thresholdValue").value=`${$("threshold").value} dBµV/m`;if(overlays.length)showOverlay()}; $("opacity").oninput=()=>{$("opacityValue").value=`${$("opacity").value}%`;overlays.forEach(layer=>layer.setOpacity(+$("opacity").value/100))};
$("stationList").onchange=()=>{updateLegend();updateDownloads();if(overlays.length)showOverlay()};
function showError(error){$("jobStatus").textContent=error.message}
loadStations().then(()=>{updateLegend();updateDownloads();if(selectedIds().length)showOverlay()}).catch(showError);
