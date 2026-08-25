import json
import sys
import time
import requests
from urllib3.exceptions import InsecureRequestWarning

# Desactivar advertencias SSL
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

BASE_URL = "https://www.laplata.gob.ar:8080/web-central/api/public/transporte"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
    'Origin': 'https://www.laplata.gob.ar',
    'Referer': 'https://www.laplata.gob.ar/'
}

session = requests.Session()
session.headers.update(HEADERS)

def get_json_robust(url, retries=3, backoff=2):
    """
    Realiza peticiones HTTP con reintentos y tolerancia a fallos.
    """
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, verify=False, timeout=20)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(f"    ⚠️ Rate limit (429). Esperando {attempt * 3}s...")
                time.sleep(attempt * 3)
            else:
                print(f"    ⚠️ HTTP {response.status_code} en {url}")
        except Exception as e:
            if attempt == retries:
                print(f"    ❌ Error definitivo en {url}: {e}")
                return None
            time.sleep(attempt * backoff)
    return None

def extraer_transporte_geojson():
    geojson_out = {
        "type": "FeatureCollection",
        "features": []
    }
    
    url_lineas = f"{BASE_URL}/obtenerLineas?page=0"
    print(f"Consultando líneas desde {url_lineas}...")
    
    lineas = get_json_robust(url_lineas)
    
    if not lineas or not isinstance(lineas, list):
        print("❌ CRÍTICO: No se pudo obtener la lista inicial de líneas.")
        # Escribir archivo mínimo para no romper el flujo
        with open("transporte_la_plata.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson_out, f, ensure_ascii=False, indent=2)
        sys.exit(1)

    print(f"✅ Se encontraron {len(lineas)} líneas. Procesando recorridos...")

    total_features = 0

    for linea in lineas:
        linea_id = linea.get("id")
        linea_nombre = linea.get("nombre", "Sin nombre")
        linea_color = linea.get("color", "#3388ff")
        
        print(f"\n🚌 Procesando Línea: {linea_nombre} (ID: {linea_id})")
        
        url_ramales = f"{BASE_URL}/obtenerRamalesPorLinea?idLinea={linea_id}"
        time.sleep(0.5)
        ramales = get_json_robust(url_ramales)

        if not ramales or not isinstance(ramales, list):
            print(f"  ⚠️ No se encontraron ramales o falló la respuesta para la línea {linea_nombre}")
            continue

        for ramal in ramales:
            ramal_id = ramal.get("id")
            ramal_nombre = ramal.get("nombre", "Sin nombre")
            
            url_detalle = f"{BASE_URL}/obtenerRamal?idRamal={ramal_id}"
            time.sleep(0.5)
            detalle = get_json_robust(url_detalle)

            if not detalle or not isinstance(detalle, dict):
                print(f"  ⚠️ No se pudo obtener el detalle del ramal '{ramal_nombre}' (ID: {ramal_id})")
                continue

            descripcion = detalle.get("descripcion", "")
            paradas_info = {}
            for p in detalle.get("paradas", []):
                if isinstance(p, dict) and p.get("codigo"):
                    paradas_info[p.get("codigo")] = p.get("nombre")

            tramo_raw = detalle.get("tramoJson")
            if tramo_raw:
                try:
                    tramo_data = json.loads(tramo_raw)
                    features = tramo_data.get("features", [])
                    
                    for feat in features:
                        geom = feat.get("geometry", {})
                        props = feat.get("properties", {})
                        
                        props["linea"] = linea_nombre
                        props["ramal"] = ramal_nombre
                        props["descripcion"] = descripcion
                        
                        props["stroke"] = linea_color
                        props["stroke-width"] = 4
                        props["stroke-opacity"] = 0.8
                        props["fill"] = linea_color

                        if geom.get("type") == "Point":
                            codigo = props.get("codigo")
                            nombre_parada = paradas_info.get(codigo, props.get("label", ""))
                            props["name"] = f"Parada: {nombre_parada}"
                            props["tipo"] = "Parada"
                        elif geom.get("type") in ["LineString", "MultiLineString"]:
                            props["name"] = f"Línea {linea_nombre} - {ramal_nombre}"
                            props["tipo"] = "Recorrido"
                            
                        geojson_out["features"].append({
                            "type": "Feature",
                            "geometry": geom,
                            "properties": props
                        })
                        total_features += 1

                    print(f"  └─ Ramal '{ramal_nombre}': {len(features)} elementos procesados.")

                except (json.JSONDecodeError, TypeError) as err:
                    print(f"  ⚠️ Error al parsear JSON del ramal '{ramal_nombre}': {err}")

    # Guardar siempre el resultado final (incluso si algunas líneas fallaron)
    output_filename = "transporte_la_plata.geojson"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(geojson_out, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 ¡Proceso completado! Se guardaron {total_features} entidades en '{output_filename}'.")

if __name__ == "__main__":
    extraer_transporte_geojson()
