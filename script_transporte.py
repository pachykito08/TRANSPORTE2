import json
import urllib.request
import urllib.error
import ssl

BASE_URL = "https://www.laplata.gob.ar:8080/web-central/api/public/transporte"

# Crear contexto SSL que ignora la validación de certificados no reconocidos/incompletos
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def get_json(url):
    """Realiza una petición HTTP GET pasando el contexto SSL omitido."""
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, context=ssl_context) as response:
        return json.loads(response.read().decode('utf-8'))

def extraer_transporte_geojson():
    geojson_out = {
        "type": "FeatureCollection",
        "features": []
    }
    
    url_lineas = f"{BASE_URL}/obtenerLineas?page=0"
    print(f"Obteniendo lista de líneas desde {url_lineas}...")
    
    try:
        lineas = get_json(url_lineas)
    except Exception as e:
        print(f"Error al obtener las líneas: {e}")
        # Se genera un archivo GeoJSON mínimo para evitar errores en Git/Actions
        with open("transporte_la_plata.geojson", "w", encoding="utf-8") as f:
            json.dump(geojson_out, f, ensure_ascii=False, indent=2)
        return

    print(f"Se encontraron {len(lineas)} líneas.")

    for linea in lineas:
        linea_id = linea.get("id")
        linea_nombre = linea.get("nombre", "")
        linea_color = linea.get("color", "#3388ff")
        
        url_ramales = f"{BASE_URL}/obtenerRamalesPorLinea?idLinea={linea_id}"
        try:
            ramales = get_json(url_ramales)
        except Exception as e:
            print(f"Error al obtener ramales de la línea {linea_nombre}: {e}")
            continue

        for ramal in ramales:
            ramal_id = ramal.get("id")
            ramal_nombre = ramal.get("nombre", "")
            
            url_detalle = f"{BASE_URL}/obtenerRamal?idRamal={ramal_id}"
            try:
                detalle = get_json(url_detalle)
            except Exception as e:
                print(f"Error al obtener detalle del ramal {ramal_nombre}: {e}")
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
    
    print(f"\n¡Proceso finalizado! Se guardó '{output_filename}'.")

if __name__ == "__main__":
    extraer_transporte_geojson()
