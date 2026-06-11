import streamlit as st

st.set_page_config(layout="wide", page_title="无人机任务规划系统")

html_code = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>无人机任务规划系统</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-draw/v1.4.0/mapbox-gl-draw.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-draw/v1.4.0/mapbox-gl-draw.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@turf/turf@6/turf.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #1a2a32; height: 100vh; overflow: hidden; color: #e0e0e0; }
        .app-container { display: flex; flex-direction: column; height: 100%; }
        .nav-bar { background: #0f1a1f; padding: 0 24px; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #2c3e3a; }
        .nav-btn { background: transparent; border: none; color: #b0bec5; font-size: 1.1rem; font-weight: 600; padding: 14px 24px; cursor: pointer; border-bottom: 3px solid transparent; }
        .nav-btn.active { color: #4caf50; border-bottom-color: #4caf50; background: rgba(76,175,80,0.1); }
        .pages-container { flex: 1; position: relative; overflow: hidden; }
        .page { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; visibility: hidden; display: flex; transition: opacity 0.25s ease; }
        .page.active-page { opacity: 1; visibility: visible; }
        .planning-layout { display: flex; width: 100%; height: 100%; background: #1e2c32; }
        .control-panel { width: 340px; background: rgba(18,28,32,0.9); backdrop-filter: blur(12px); border-right: 1px solid #2c4a4a; padding: 20px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 20px; z-index: 2; }
        .map-container { flex: 1; }
        #map { width: 100%; height: 100%; }
        .card { background: #0f1a1ecc; border-radius: 16px; padding: 16px; border: 1px solid #2c5a5a; }
        .card h3 { font-size: 1rem; margin-bottom: 12px; border-left: 4px solid #4caf50; padding-left: 10px; color: #ccffcc; }
        .input-group { margin-bottom: 14px; display: flex; flex-direction: column; gap: 6px; }
        input, select, button { background: #1e2f38; border: 1px solid #2e6b6b; padding: 8px 12px; border-radius: 8px; color: #f0f0f0; font-size: 0.9rem; outline: none; }
        button { background: #2c5a5a; cursor: pointer; font-weight: bold; margin-top: 6px; }
        button:hover { background: #3e7e7e; }
        .danger-btn { background: #8b3c3c; }
        .waypoint-list { max-height: 150px; overflow-y: auto; background: #071013; border-radius: 8px; padding: 6px; margin-top: 8px; }
        .waypoint-item { display: flex; justify-content: space-between; padding: 4px 8px; border-bottom: 1px solid #2c5a5a; font-size: 0.75rem; }
        .monitor-layout { width: 100%; height: 100%; background: #111d22; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 24px; }
        .monitor-card { background: #0e181c; border-radius: 24px; border: 1px solid #2b6b5e; padding: 20px; }
        .gauge-group { display: flex; flex-wrap: wrap; gap: 24px; margin-top: 16px; }
        .gauge-item { background: #071013; padding: 12px 20px; border-radius: 16px; min-width: 160px; }
        .gauge-label { font-size: 0.7rem; color: #8aa0a0; }
        .gauge-value { font-size: 1.6rem; font-weight: bold; color: #4caf50; }
        .heartbeat-log { background: #071013; border-radius: 16px; max-height: 260px; overflow-y: auto; font-family: monospace; font-size: 0.75rem; }
        .heartbeat-item { padding: 8px 12px; border-bottom: 1px solid #1e4e4a; display: flex; gap: 16px; flex-wrap: wrap; }
        .sim-control-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
        .coord-note { font-size: 0.7rem; color: #8aa0a0; margin-top: 4px; }
    </style>
</head>
<body>
<div class="app-container">
    <div class="nav-bar">
        <button class="nav-btn active" data-page="planning">🗺️ 航线规划</button>
        <button class="nav-btn" data-page="monitor">📡 飞行监控</button>
        <div style="flex:1"></div>
        <div style="font-size:12px; background:#1e3a3a; padding:4px 12px; border-radius:20px;">🧭 坐标系: <span id="globalCoordSysLabel">WGS-84</span></div>
    </div>
    <div class="pages-container">
        <div id="planningPage" class="page active-page">
            <div class="planning-layout">
                <div class="control-panel">
                    <div class="card"><h3>📍 坐标系设置</h3><div class="input-group"><select id="coordSysSelect"><option value="WGS-84" selected>WGS-84 (GPS)</option><option value="GCJ-02">GCJ-02 (高德/百度)</option></select><div class="coord-note">地图底图WGS-84，坐标自动转换</div></div></div>
                    <div class="card"><h3>✈️ 航点规划</h3><div class="input-group"><div style="display:flex;gap:8px;"><input type="text" id="newWpLng" placeholder="经度"><input type="text" id="newWpLat" placeholder="纬度"><button id="addWpBtn" style="margin-top:0;">➕ 添加</button></div><button id="clearWpBtn" class="danger-btn">🗑️ 清空所有航点</button></div><div class="waypoint-list" id="waypointList"></div><div class="param-row"><span>🟢 安全半径 (米)</span><input type="number" id="safetyRadius" value="30" step="5" style="width:100px;"></div><button id="checkSafetyBtn">⚠️ 检测航线与障碍物距离</button><div id="safetyResult" style="margin-top:8px; font-size:0.75rem; color:#ffaa66;"></div></div>
                    <div class="card"><h3>⚠️ 障碍物管理 (圈选)</h3><button id="drawObstacleBtn">✏️ 开始绘制障碍物</button><button id="clearObstaclesBtn" class="danger-btn" style="margin-top:6px;">🗑️ 清除全部障碍物</button><div id="obstacleList" style="margin-top:8px; max-height:120px; overflow-y:auto; font-size:0.7rem;"></div><div class="coord-note">双击地图完成绘制，障碍物自动保存</div></div>
                </div>
                <div class="map-container"><div id="map"></div></div>
            </div>
        </div>
        <div id="monitorPage" class="page">
            <div class="monitor-layout">
                <div class="monitor-card"><h2>📡 飞行模拟监控</h2><div class="sim-control-bar"><button id="startSimBtn" style="background:#2e7d32;">▶️ 开始飞行</button><button id="pauseSimBtn">⏸️ 暂停</button><button id="resetSimBtn">🔄 重置</button><div>飞行速度: <input type="range" id="speedSlider" min="0.5" max="10" step="0.5" value="3"> <span id="speedVal">3</span> m/s</div></div><div class="gauge-group"><div class="gauge-item"><div class="gauge-label">当前航点</div><div class="gauge-value" id="currentWp">0 / 0</div></div><div class="gauge-item"><div class="gauge-label">实时高度</div><div class="gauge-value" id="simAltitude">50 m</div></div><div class="gauge-item"><div class="gauge-label">飞行速度</div><div class="gauge-value" id="simSpeed">0 m/s</div></div><div class="gauge-item"><div class="gauge-label">已用时间</div><div class="gauge-value" id="elapsedTime">0 s</div></div><div class="gauge-item"><div class="gauge-label">剩余距离</div><div class="gauge-value" id="remainingDist">0 m</div></div><div class="gauge-item"><div class="gauge-label">预计到达</div><div class="gauge-value" id="eta">0 s</div></div><div class="gauge-item"><div class="gauge-label">电量模拟</div><div class="gauge-value" id="batteryLevel">100%</div></div></div></div>
                <div class="monitor-card"><h3>💓 心跳包数据流</h3><div class="heartbeat-log" id="heartbeatLog"><div style="padding:20px; text-align:center;">等待飞行开始...</div></div></div>
            </div>
        </div>
    </div>
</div>
<script>
    const PI=Math.PI, A=6378245.0, EE=0.00669342162296594323;
    function transformLat(x,y){let ret=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*Math.sqrt(Math.abs(x)); ret+=(20*Math.sin(6*x*PI)+20*Math.sin(2*x*PI))*2/3; ret+=(20*Math.sin(y*PI)+40*Math.sin(y/3*PI))*2/3; ret+=(160*Math.sin(y/12*PI)+320*Math.sin(y*PI/30))*2/3; return ret;}
    function transformLon(x,y){let ret=300+x+2*y+0.1*x*x+0.1*x*y+0.1*Math.sqrt(Math.abs(x)); ret+=(20*Math.sin(6*x*PI)+20*Math.sin(2*x*PI))*2/3; ret+=(20*Math.sin(x*PI)+40*Math.sin(x/3*PI))*2/3; ret+=(150*Math.sin(x/12*PI)+300*Math.sin(x/30*PI))*2/3; return ret;}
    function outOfChina(lng,lat){return lng<72.004||lng>137.8347||lat<0.8293||lat>55.8271;}
    function gcj02_to_wgs84(lng,lat){if(outOfChina(lng,lat)) return[lng,lat]; let dlat=transformLat(lng-105,lat-35), dlng=transformLon(lng-105,lat-35); let radlat=lat/180*PI, magic=Math.sin(radlat); magic=1-EE*magic*magic; let sqrtmagic=Math.sqrt(magic); dlat=(dlat*180)/((A*(1-EE))/(magic*sqrtmagic)*PI); dlng=(dlng*180)/(A/sqrtmagic*Math.cos(radlat)*PI); return [lng*2-(lng+dlng), lat*2-(lat+dlat)];}
    function wgs84_to_gcj02(lng,lat){if(outOfChina(lng,lat)) return[lng,lat]; let dlat=transformLat(lng-105,lat-35), dlng=transformLon(lng-105,lat-35); let radlat=lat/180*PI, magic=Math.sin(radlat); magic=1-EE*magic*magic; let sqrtmagic=Math.sqrt(magic); dlat=(dlat*180)/((A*(1-EE))/(magic*sqrtmagic)*PI); dlng=(dlng*180)/(A/sqrtmagic*Math.cos(radlat)*PI); return [lng+dlng, lat+dlat];}
    
    mapboxgl.accessToken = 'pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4M29iazA2Z2gycXA4N2pmbDZmangifQ.-g_vE53SD2WrJ6t-r7mQPQ';
    let map, draw, waypoints=[], obstacles=[], waypointMarkers=[], aircraftMarker=null, simInterval=null, simActive=false, simProgress=0, totalRouteLength=0, segmentLengths=[], flightSpeed=3, simStartTime=0;
    
    function getDisplayCoords(lngWGS,latWGS){let sys=document.getElementById('coordSysSelect').value; if(sys==='GCJ-02') return wgs84_to_gcj02(lngWGS,latWGS); return [lngWGS,latWGS];}
    function computeRouteMetrics(){if(waypoints.length<2){totalRouteLength=0; segmentLengths=[]; return 0;} let lengths=[], total=0; for(let i=0;i<waypoints.length-1;i++){let p1=waypoints[i],p2=waypoints[i+1]; let dist=turf.distance(turf.point([p1.lng,p1.lat]),turf.point([p2.lng,p2.lat]),{units:'meters'}); lengths.push(dist); total+=dist;} segmentLengths=lengths; totalRouteLength=total; return total;}
    function getPositionAtProgress(progress){if(waypoints.length<2) return null; let targetDist=progress*totalRouteLength, accum=0; for(let i=0;i<segmentLengths.length;i++){if(targetDist<=accum+segmentLengths[i]){let t=(targetDist-accum)/segmentLengths[i]; let p1=waypoints[i],p2=waypoints[i+1]; return{lng:p1.lng+(p2.lng-p1.lng)*t, lat:p1.lat+(p2.lat-p1.lat)*t, segIdx:i, t};} accum+=segmentLengths[i];} return waypoints[waypoints.length-1];}
    function updateAircraftMarker(pos){if(!aircraftMarker){let el=document.createElement('div'); el.innerHTML='✈️'; el.style.fontSize='24px'; aircraftMarker=new mapboxgl.Marker(el).setLngLat([pos.lng,pos.lat]).addTo(map);}else{aircraftMarker.setLngLat([pos.lng,pos.lat]);}}
    function addHeartbeatLog(msg,latLon,alt,bat){let container=document.getElementById('heartbeatLog'); let now=new Date().toLocaleTimeString(); let div=document.createElement('div'); div.className='heartbeat-item'; div.innerHTML=`<span class="heartbeat-time">${now}</span><span>📍 ${latLon}</span><span>📏 ${alt}m</span><span>🔋 ${bat}%</span><span>${msg}</span>`; container.prepend(div); if(container.children.length>30) container.removeChild(container.lastChild);}
    function updateMonitorDisplay(currentDist,elapsedSec,remainingDist,etaSec,battery,altitude,speed,wpIdx,totalWp){document.getElementById('currentWp').innerText=`${wpIdx} / ${totalWp}`; document.getElementById('simAltitude').innerText=altitude+" m"; document.getElementById('simSpeed').innerText=speed.toFixed(1)+" m/s"; document.getElementById('elapsedTime').innerText=elapsedSec.toFixed(1)+" s"; document.getElementById('remainingDist').innerText=remainingDist.toFixed(0)+" m"; document.getElementById('eta').innerText=etaSec.toFixed(1)+" s"; document.getElementById('batteryLevel').innerText=battery+"%";}
    function startSimulation(){if(simInterval) clearInterval(simInterval); if(waypoints.length<2){alert("请先在航线规划中添加至少两个航点"); return;} computeRouteMetrics(); if(totalRouteLength<=0) return; simActive=true; simProgress=0; simStartTime=performance.now()/1000; const altitude=50; const speed=flightSpeed; simInterval=setInterval(()=>{if(!simActive) return; let now=performance.now()/1000; let elapsed=now-simStartTime; let expectedDist=speed*elapsed; let newProgress=Math.min(1,expectedDist/totalRouteLength); if(newProgress>=1){simProgress=1; clearInterval(simInterval); simInterval=null; simActive=false; let finalPos=waypoints[waypoints.length-1]; updateAircraftMarker(finalPos); let[dispLng,dispLat]=getDisplayCoords(finalPos.lng,finalPos.lat); addHeartbeatLog("飞行完成",`${dispLat.toFixed(6)}, ${dispLng.toFixed(6)}`,altitude,98); updateMonitorDisplay(totalRouteLength,elapsed,0,0,98,altitude,speed,waypoints.length,waypoints.length); return;} simProgress=newProgress; let pos=getPositionAtProgress(simProgress); if(pos){updateAircraftMarker({lng:pos.lng,lat:pos.lat}); let remaining=totalRouteLength-(simProgress*totalRouteLength); let eta=remaining/speed; let battery=Math.max(60,100-Math.floor(simProgress*40)); let[dispLng,dispLat]=getDisplayCoords(pos.lng,pos.lat); addHeartbeatLog("飞行中",`${dispLat.toFixed(6)}, ${dispLng.toFixed(6)}`,altitude,battery); let wpIdx=1, accum=0; for(let i=0;i<segmentLengths.length;i++){if(simProgress*totalRouteLength>accum+segmentLengths[i]) accum+=segmentLengths[i]; else{wpIdx=i+1; break;}} updateMonitorDisplay(simProgress*totalRouteLength,elapsed,remaining,eta,battery,altitude,speed,wpIdx,waypoints.length);}},200);}
    function stopSimulation(){if(simInterval){clearInterval(simInterval); simInterval=null;} simActive=false;}
    function resetSimulation(){stopSimulation(); if(waypoints.length){simProgress=0; let startPos=waypoints[0]; updateAircraftMarker(startPos); let[dlng,dlat]=getDisplayCoords(startPos.lng,startPos.lat); addHeartbeatLog("重置至起点",`${dlat.toFixed(6)}, ${dlng.toFixed(6)}`,50,100); updateMonitorDisplay(0,0,totalRouteLength,totalRouteLength/flightSpeed,100,50,flightSpeed,1,waypoints.length);}}
    function updateWaypointsUI(){let container=document.getElementById('waypointList'); container.innerHTML=waypoints.map((wp,idx)=>`<div class="waypoint-item">航点${idx+1}: ${wp.lat.toFixed(6)}, ${wp.lng.toFixed(6)} <button class="btn-sm" onclick="removeWaypoint(${idx})">❌</button></div>`).join(''); waypointMarkers.forEach(m=>m.remove()); waypointMarkers=[]; waypoints.forEach(wp=>{let el=document.createElement('div'); el.innerHTML='📍'; el.style.fontSize='18px'; let marker=new mapboxgl.Marker(el).setLngLat([wp.lng,wp.lat]).addTo(map); waypointMarkers.push(marker);}); drawRouteLine(); computeRouteMetrics();}
    function drawRouteLine(){if(!map.getSource('route')){map.addSource('route',{type:'geojson',data:{type:'Feature',geometry:{type:'LineString',coordinates:[]}}}); map.addLayer({id:'route-line',type:'line',source:'route',paint:{'line-color':'#4caf50','line-width':4}});} if(waypoints.length>=2){const coords=waypoints.map(wp=>[wp.lng,wp.lat]); map.getSource('route').setData({type:'Feature',geometry:{type:'LineString',coordinates:coords}});} else{map.getSource('route').setData({type:'Feature',geometry:{type:'LineString',coordinates:[]}});}}
    function initDraw(){draw=new MapboxDraw({displayControlsDefault:false,controls:{polygon:true,trash:true}}); map.addControl(draw); let saved=localStorage.getItem('drone_obstacles'); if(saved){obstacles=JSON.parse(saved); obstacles.forEach(geom=>{map.addSource(`obs-${Date.now()}-${Math.random()}`,{type:'geojson',data:{type:'Feature',geometry:geom}}); map.addLayer({id:`obs-layer-${Date.now()}-${Math.random()}`,type:'fill',source:{type:'geojson',data:geom},paint:{'fill-color':'#ff4d4d','fill-opacity':0.5}});}); updateObstacleListUI();} map.on('draw.create',updateObstaclesFromDraw); map.on('draw.delete',updateObstaclesFromDraw); map.on('draw.update',updateObstaclesFromDraw);}
    function updateObstaclesFromDraw(){let data=draw.getAll(); let polys=data.features.filter(f=>f.geometry.type==='Polygon'); obstacles=polys.map(f=>f.geometry); localStorage.setItem('drone_obstacles',JSON.stringify(obstacles)); let existingLayers=map.getStyle().layers.filter(l=>l.id.startsWith('obs-layer-')); existingLayers.forEach(l=>map.removeLayer(l.id)); obstacles.forEach((geom,idx)=>{let srcId=`obs-src-${idx}`; if(map.getSource(srcId)) map.removeSource(srcId); map.addSource(srcId,{type:'geojson',data:{type:'Feature',geometry:geom}}); map.addLayer({id:`obs-layer-${idx}`,type:'fill',source:srcId,paint:{'fill-color':'#ff4d4d','fill-opacity':0.5,'fill-outline-color':'#ff0000'}});}); updateObstacleListUI();}
    function updateObstacleListUI(){let div=document.getElementById('obstacleList'); div.innerHTML=obstacles.map((_,idx)=>`<div>障碍物 ${idx+1} <button onclick="removeObstacle(${idx})">删除</button></div>`).join('');}
    window.removeObstacle=function(idx){obstacles.splice(idx,1); localStorage.setItem('drone_obstacles',JSON.stringify(obstacles)); updateObstaclesFromDraw(); draw.deleteAll(); obstacles.forEach(geom=>{draw.add({type:'Feature',geometry:geom});});};
    window.removeWaypoint=function(idx){waypoints.splice(idx,1); updateWaypointsUI();};
    function checkSafety(){if(waypoints.length<2){document.getElementById('safetyResult').innerHTML="⚠️ 请先添加航点"; return;} let radius=parseFloat(document.getElementById('safetyRadius').value); let unsafeSegments=[]; for(let i=0;i<waypoints.length-1;i++){let p1=waypoints[i],p2=waypoints[i+1]; let line=turf.lineString([[p1.lng,p1.lat],[p2.lng,p2.lat]]); for(let obs of obstacles){let poly=turf.polygon(obs.coordinates); let dist=turf.pointToLineDistance(turf.point([p1.lng,p1.lat]),line,{units:'meters'}); let dist2=turf.pointToLineDistance(turf.point([p2.lng,p2.lat]),line,{units:'meters'}); let minDist=Math.min(dist,dist2); if(turf.booleanIntersects(line,poly)) minDist=0; if(minDist<radius) unsafeSegments.push(`段 ${i+1} 距离障碍物 ${minDist.toFixed(1)}m`);}} let resultDiv=document.getElementById('safetyResult'); if(unsafeSegments.length) resultDiv.innerHTML="❌ 不安全: "+unsafeSegments.join('; '); else resultDiv.innerHTML="✅ 所有航段与障碍物保持安全距离";}
    function initMap(){map=new mapboxgl.Map({container:'map',style:'mapbox://styles/mapbox/satellite-streets-v12',center:[118.749,32.2332],zoom:16.5,pitch:50}); map.on('load',()=>{initDraw(); map.on('click',(e)=>{let lng=e.lngLat.lng,lat=e.lngLat.lat; waypoints.push({lng,lat}); updateWaypointsUI();});});}
    document.getElementById('addWpBtn').onclick=()=>{let lng=parseFloat(document.getElementById('newWpLng').value),lat=parseFloat(document.getElementById('newWpLat').value); if(isNaN(lng)||isNaN(lat)) return alert("输入有效经纬度"); let sys=document.getElementById('coordSysSelect').value; if(sys==='GCJ-02'){[lng,lat]=gcj02_to_wgs84(lng,lat);} waypoints.push({lng,lat}); updateWaypointsUI();};
    document.getElementById('clearWpBtn').onclick=()=>{waypoints=[]; updateWaypointsUI();};
    document.getElementById('drawObstacleBtn').onclick=()=>{draw.changeMode('draw_polygon');};
    document.getElementById('clearObstaclesBtn').onclick=()=>{localStorage.removeItem('drone_obstacles'); obstacles=[]; draw.deleteAll(); updateObstaclesFromDraw();};
    document.getElementById('checkSafetyBtn').onclick=checkSafety;
    document.getElementById('startSimBtn').onclick=()=>{if(waypoints.length>=2) startSimulation(); else alert("至少两个航点");};
    document.getElementById('pauseSimBtn').onclick=()=>{simActive=false; if(simInterval){clearInterval(simInterval); simInterval=null;}};
    document.getElementById('resetSimBtn').onclick=resetSimulation;
    let speedSlider=document.getElementById('speedSlider'); speedSlider.oninput=()=>{flightSpeed=parseFloat(speedSlider.value); document.getElementById('speedVal').innerText=flightSpeed;};
    document.getElementById('coordSysSelect').onchange=()=>{document.getElementById('globalCoordSysLabel').innerText=document.getElementById('coordSysSelect').value;};
    window.onload=initMap;
</script>
</body>
</html>
"""

st.components.v1.html(html_code, height=800, scrolling=True)
