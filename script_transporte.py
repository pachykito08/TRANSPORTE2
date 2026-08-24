import json
import urllib.request
import urllib.error
import ssl
import sys

BASE_URL = "https://www.laplata.gob.ar:8080/web-central/api/public/transporte"

# Desactivar verificación SSL por certificados incompletos en el servidor de destino
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Referer': 'https://www.laplata.gob.ar/',
    'Connection': 'keep-alive'
}

def get_json(url):
    """Petición HTTP GET con cabeceras completas de navegador."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
        content = response.read().decode('utf-8')
        return json.loads(content)

def extraer_transporte_geojson():
    geojson_out = {
        "type": "FeatureCollection",
        "features": []
    }
    
    url_lineas = f"{BASE_URL}/obtenerLineas?page=0"
    print(f"Obteniendo lista de líneas desde {url_lineas}...")
    
    try:
        lineas = get_json(url_lineas)
    except urllib.error.HTTPError as e:
        print(f"ERROR HTTP al obtener líneas: Código {e.code} - {e.reason}")
        # Hacemos que el paso de GitHub Actions falle de forma explícita para revisar los logs
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR DE CONEXIÓN al obtener líneas: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR INESPERADO: {type(e).__name__} - {e}")
        sys.exit(1)

    print(f"Se encontraron {len(lineas)} líneas.")

    for linea in lineas:
        linea_id = linea.get("id")
        linea_nombre = linea.get("nombre", "")
        linea_color = linea.get("color", "#3388ff")
        
        url_ramales = f"{BASE_URL}/obtenerRamalesPorLinea?idLinea={linea_id}"
        try:
            ramales = get_json(url_ramales)
        except Exception as e:
            print(f"Error en ramales de línea {linea_nombre} (ID: {linea_id}): {e}")
            continue

        for ramal in ramales:
            ramal_id = ramal.get("id")
            ramal_nombre = ramal.get("nombre", "")
            
            url_detalle = f"{BASE_URL}/obtenerRamal?idRamal={ramal_id}"
            try:
                detalle = get_json(url_detalle)
            except Exception as e:
                print(f"Error en detalle de ramal {ramal_nombre} (ID: {ramal_id}): {e}")
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
                    print(f"No se pudo parsear `tramoJson` para ramal ID {ramal_id}")

    output_filename = "transporte_la_plata.geojson"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(geojson_out, f, ensure_ascii=False, indent=2)
    
    print(f"\n¡Éxito! Archivo '{output_filename}' generado con {len(geojson_out['features'])} elementos.")

if __name__ == "__main__":
    extraer_transporte_geojson()
