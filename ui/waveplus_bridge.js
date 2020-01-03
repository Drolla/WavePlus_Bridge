/*************************************************************************
* Airthings Wave Plus bridge to Wifi/LAN
**************************************************************************
* waveplus_bridge.js - Wave Plus bridge JavaScript AJAX module
* 
* Copyright (C) 2020 Andreas Drollinger
*************************************************************************/

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

function LoadData(Url,DivId) {
	AjaxJsonGet(Url,function(JsonData) {
		jsonURL = window.location.origin+"/data"
		innerHTML = "Data in JSON format: <a href=\""+jsonURL+"\">"+jsonURL+"</a>"
		currentTime = JsonData["current_time"]
		for(var Key0 in JsonData["devices"]) {
			innerHTML += 
					"<h2>"+Key0+"</h2>"+
					"<table><thead><tr></tr></thead><tbody>";
			JsonArray1 = JsonData["devices"][Key0]
			for(var Key1 in JsonArray1) {
				if (Key1=="update_time") {
					innerHTML += 
							"<tr><td>updated</td><td>"+(currentTime-JsonArray1[Key1])+"s</tr>";
				} else {
					innerHTML += 
						"<tr><td>"+Key1+"</td><td>"+JsonArray1[Key1]+"</tr>";
				}
			}
			innerHTML += 
					"</tbody></table>";
		}
		document.getElementById(DivId).innerHTML = innerHTML;
	});
}
