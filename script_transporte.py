import json
import sys
import requests
from urllib3.exceptions import InsecureRequestWarning

# Desactivar advertencias de SSL inseguro
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

BASE_URL = "https://www.laplata.gob.ar:8080/web-central/api/public/transporte"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
    'Origin': 'https://www.laplata.gob.ar',
    'Referer': 'https://www.laplata.gob.ar/'
}

# Lista de proxies públicos/reversos de respaldo si falla la conexión directa
PROXIES_LIST = [
    None,  # Intento directo primero
    {"http": "http://181.118.170.18:8080", "https": "http://181.118.170.18:8080"}, # Proxy Argentina
    {"http": "http://190.210.217.186:999", "https": "http://190.210.217.186:999"}
]

def get_json_con_reintentos(url):
    """Realiza peticiones probando conexión directa y saltando a proxies si hay timeout."""
    for proxy in PROXIES_LIST:
        try:
            response = requests.get(
                url, 
                headers=HEADERS, 
                verify=False, 
                timeout=12, 
                proxies=proxy
            )
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            continue
            
    raise TimeoutError("No se pudo conectar a la API de La Plata incluso tras usar proxies.")

def extraer_transporte_geojson():
    geojson_out = {
        "type": "FeatureCollection",
        "features": []
    }
    
    url_lineas = f"{BASE_URL}/obtenerLineas?page=0"
    print(f"Obteniendo lista de líneas desde {url_lineas}...")
    
    try:
        lineas = get_json_con_reintentos(url_lineas)
    except Exception as e:
        print(f"ERROR CRÍTICO: {e}")
        sys.exit(1)

    print(f"Se encontraron {len(lineas)} líneas.")

    for linea in lineas:
        linea_id = linea.get("id")
        linea_nombre = linea.get("nombre", "")
        linea_color = linea.get("color", "#3388ff")
        
        url_ramales = f"{BASE_URL}/obtenerRamalesPorLinea?idLinea={linea_id}"
        try:
            ramales = get_json_con_reintentos(url_ramales)
        except Exception as e:
            print(f"Error en ramales de línea {linea_nombre}: {e}")
            continue

        for ramal in ramales:
            ramal_id = ramal.get("id")
            ramal_nombre = ramal.get("nombre", "")
            
            url_detalle = f"{BASE_URL}/obtenerRamal?idRamal={ramal_id}"
            try:
                detalle = get_json_con_reintentos(url_detalle)
            except Exception as e:
                print(f"Error en detalle de ramal {ramal_nombre}: {e}")
                continue

            descripcion = detalle.get("descripcion", "")
            paradas_info = {p.get("codigo"): p.get("nombre") for p in detalle.get("paradas", [])}

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
                except json.JSONDecodeError:
                    pass

    output_filename = "transporte_la_plata.geojson"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(geojson_out, f, ensure_ascii=False, indent=2)
    
    print(f"\n¡Éxito! GeoJSON generado con {len(geojson_out['features'])} entidades.")

if __name__ == "__main__":
    extraer_transporte_geojson()
