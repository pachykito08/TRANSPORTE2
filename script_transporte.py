import json
import sys
import time
import requests
from urllib3.exceptions import InsecureRequestWarning

# Desactivar advertencias de SSL inseguro
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

BASE_URL = "https://www.laplata.gob.ar:8080/web-central/api/public/transporte"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
    'Referer': 'https://www.laplata.gob.ar/'
}

# Inicializar sesión HTTP para reutilizar conexiones
session = requests.Session()
session.headers.update(HEADERS)

def get_json_robust(url, retries=3, backoff_factor=1.5):
    """
    Consulta la API con reintentos automáticos y pausa entre fallos
    para evitar ser bloqueado por Rate Limiting.
    """
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, verify=False, timeout=15)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Too Many Requests
                print(f"  [Rate Limit] Esperando para reintentar (Intento {attempt}/{retries})...")
                time.sleep(attempt * 3)
            else:
                print(f"  [HTTP {response.status_code}] Error al consultar {url}")
        except requests.exceptions.RequestException as e:
            if attempt == retries:
                raise e
            print(f"  [Fallo de red] Reintentando en {attempt * backoff_factor}s... ({e})")
            time.sleep(attempt * backoff_factor)
            
    raise Exception(f"No se pudo obtener respuesta de {url} tras {retries} intentos.")

def extraer_transporte_geojson():
    geojson_out = {
        "type": "FeatureCollection",
        "features": []
    }
    
    url_lineas = f"{BASE_URL}/obtenerLineas?page=0"
    print(f"Obteniendo lista de líneas desde {url_lineas}...")
    
    try:
        lineas = get_json_robust(url_lineas)
    except Exception as e:
        print(f"ERROR CRÍTICO al obtener líneas: {e}")
        sys.exit(1)

    print(f"Se encontraron {len(lineas)} líneas. Procesando recorridos...")

    for linea in lineas:
        linea_id = linea.get("id")
        linea_nombre = linea.get("nombre", "")
        linea_color = linea.get("color", "#3388ff")
        
        print(f"\nProcesando Línea: {linea_nombre} (ID: {linea_id})...")
        
        url_ramales = f"{BASE_URL}/obtenerRamalesPorLinea?idLinea={linea_id}"
        try:
            # Pausa de 0.5s para respetar Rate Limiting
            time.sleep(0.5)
            ramales = get_json_robust(url_ramales)
        except Exception as e:
            print(f"  -> Error al obtener ramales de la línea {linea_nombre}: {e}")
            continue

        for ramal in ramales:
            ramal_id = ramal.get("id")
            ramal_nombre = ramal.get("nombre", "")
            
            url_detalle = f"{BASE_URL}/obtenerRamal?idRamal={ramal_id}"
            try:
                time.sleep(0.5)
                detalle = get_json_robust(url_detalle)
            except Exception as e:
                print(f"  -> Error en detalle de ramal {ramal_nombre} (ID: {ramal_id}): {e}")
                continue

            descripcion = detalle.get("descripcion", "")
            paradas_info = {p.get("codigo"): p.get("nombre") for p in detalle.get("paradas", []) if p.get("codigo")}

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
    
    print(f"\n¡Éxito! GeoJSON generado con {len(geojson_out['features'])} elementos.")

if __name__ == "__main__":
    extraer_transporte_geojson()
