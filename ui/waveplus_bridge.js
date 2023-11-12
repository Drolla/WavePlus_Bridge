/*************************************************************************
* Airthings Wave Plus bridge to Wifi/LAN
**************************************************************************
* waveplus_bridge.js - Wave Plus bridge JavaScript AJAX module
* 
* Copyright (C) 2020 Andreas Drollinger
*************************************************************************/

var DisplayType="Classic";

function Ajax(Method,Url,Body,Callback) {
	var xHttp = new XMLHttpRequest();
	xHttp.onreadystatechange = function() { 
		if (xHttp.readyState==4 && xHttp.status==200)
			Callback(xHttp.responseText);
	}
	xHttp.open(Method,Url,true);
	xHttp.send(Body==""?null:Body);
}

function AjaxJsonGet(Url,Callback) {
	Ajax("GET",Url,"",function(responseText) {
		Callback(JSON.parse(responseText));
	});
}

function LoadTable(Url,DivId) {
	AjaxJsonGet(Url,function(JsonData) {
		jsonURL = window.location.origin+"/data"
		currentTime = JsonData["current_time"]

		allParameters = [];
		for(var DeviceName in JsonData["devices"]) {
			ParameterArray = JsonData["devices"][DeviceName]
			for(var Parameter in ParameterArray) {
				if (!allParameters.includes(Parameter)) {
					allParameters.push(Parameter);
				}
			}
		}

		innerHTML = "<table><thead><tr><td></td>";
		for(var DeviceName in JsonData["devices"]) {
			innerHTML += "<th>"+DeviceName+"</th>";
		}
		innerHTML += "</tr><tr></tr></thead><tbody>";

		for (ParIndex = 0; ParIndex < allParameters.length; ParIndex++) { 
			Parameter = allParameters[ParIndex];
			innerHTML += "<tr><td>"+Parameter+"</td>";
			for(var DeviceName in JsonData["devices"]) {
				deviceDataArray = JsonData["devices"][DeviceName];
				if (!(Parameter in deviceDataArray)) {
					innerHTML += "<td></td>";
				} else if (Parameter=="update_time") {
					innerHTML += "<td>"+(currentTime-deviceDataArray[Parameter])+"s</td>";
				} else {
					innerHTML += 
						"<td>"+deviceDataArray[Parameter]+"</td>";
				}
			}
			innerHTML += "</tr>";
		}
		innerHTML += "</tbody></table>";
		innerHTML += "<br>Data in JSON format: <a href=\""+jsonURL+"\">"+jsonURL+"</a>"
		document.getElementById(DivId).innerHTML = innerHTML;
	});
}

function LoadGraphs(Url,DivId) {
	var graphList =	[
		["Radon", "graph_radon", "/csv?*:radon_st*", "Bq/m3"],
		["Temperature", "graph_temp", "/csv?*:temp*", "°C"],
		["Humidity", "graph_hum", "/csv?*:hum*", "%rH"],
		["CO2", "graph_co2", "/csv?*:co2*", "hPa"],
		["VOC", "graph_voc", "/csv?*:voc*", "ppm"],
		["Pressure", "graph_pressure", "/csv?*:pressure*", "mBar"],
	];

	var innerHTML = "";
	graphList.forEach(function (item, index) {
		//innerHTML += "<h3>"+item[0]+"</h3>" +
		innerHTML += '<div id="'+item[1]+'" class="graph_container">' +
							 '<div id="'+item[1]+'_label" class="graph_label"></div>' + 
		                '<div id="'+item[1]+'_graph" class="graph_div"></div>' + 
		              '</div>';
	});
	document.getElementById(DivId).innerHTML = innerHTML;
	
	var gs = [];
	var currentTime = Date.now();

	function LoadGraphsNextGraph() {
		if (graphList.length==0) {
			Dygraph.synchronize(gs, {
				selection: false,
				zoom: true,
				range: false
			});
			return;
		}
		item = graphList.shift();
		gs.push(new Dygraph(
			document.getElementById(item[1]+'_graph'),
			item[2], {
				title: item[0],
				//legend: 'never',
				labelsSeparateLines: true,
				labelsDiv: document.getElementById(item[1]+'_label'),
				ylabel: item[3],
				showRangeSelector: gs.length%2==0,
				rangeSelectorHeight: (DisplayType=="Mobile" ? 60 : 30),
				rangeSelectorPlotLineWidth : 3,
				strokeWidth: (DisplayType=="Mobile" ? 4 : 2),
				//pointSize: 6,
				//height: 300,
				axisLabelFontSize: (DisplayType=="Mobile" ? 24 : 14),
				dateWindow: [currentTime-24*3600*1000, currentTime],
				//rollPeriod: 32,
/*				labels: [ 'Date', 'Y1', 'Y2', 'Y3', 'Y4' ],
				series : {
					'Y1': {axis: 'y'},
					'Y2': {axis: 'y2'},
				} */
			}
		));
		gs[gs.length-1].ready(LoadGraphsNextGraph);
	};
	LoadGraphsNextGraph();
}
